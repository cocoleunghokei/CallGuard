"""Replay scenario beats against local Ollama: python -m callguard.detection.eval.

Only script IDs, risk, scores, tactics and timing are printed. Transcript text
never appears in the table or error messages. With `-v` (eval-suite §8) each beat
also shows the model's own evidence quotes (<= 80 chars, from the synthetic
scripts only) and whether each one was kept or why it was dropped.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Iterable

from callguard.shared.contracts import TACTICS

from . import check
from .ollama_client import Post, _default_post
from .parse import MAX_QUOTE, _load_object, find_in_caller, split_window
from .rules import load_rules

DEFAULT_SCRIPTS = Path(__file__).resolve().parents[2] / "tests" / "detection" / "scripts"


def read_script(path: Path) -> tuple[dict[str, str], list[tuple[str, str]]]:
    headers: dict[str, str] = {}
    lines: list[tuple[str, str]] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if raw.startswith("#"):
            key, sep, value = raw[1:].partition(":")
            if sep:
                headers[key.strip()] = value.split("  #")[0].strip()
        elif raw.strip():
            speaker, sep, speech = raw.partition(":")
            if sep and speaker.strip() in ("caller", "you"):
                lines.append((speaker.strip(), speech.strip()))
    if not headers.get("id") or not headers.get("expect"):
        raise ValueError(f"invalid script header: {path.name}")
    return headers, lines


def _recording(post: Post | None) -> tuple[Post, dict]:
    """Wrap the transport so -v can see the raw reply or the error type."""
    seen: dict = {}

    def send(url: str, payload: dict, timeout: float | None = None) -> dict:
        seen.clear()
        try:
            reply = (post or _default_post())(url, payload, timeout=timeout)
        except Exception as exc:
            seen["error"] = type(exc).__name__
            raise
        seen["reply"] = reply
        return reply

    return send, seen


def _short(quote: object) -> str:
    text = " ".join(str(quote).split())
    return '"' + (text if len(text) <= MAX_QUOTE else text[:MAX_QUOTE - 1] + "…") + '"'


def diagnose(seen: dict, window: str, timeout_ms: float) -> list[str]:
    """Explain one beat: fallback cause, or each evidence item kept/dropped and why."""
    if "error" in seen:
        return [f"fallback: model call failed ({seen['error']}) after {timeout_ms / 1000:.1f} s"]
    reply = seen.get("reply")
    if not isinstance(reply, dict):
        return ["fallback: no reply from the model transport"]
    notes = []
    if reply.get("done_reason") == "length":
        notes.append("warning: reply hit num_predict and was cut off")
    obj = _load_object((reply.get("message") or {}).get("content"))
    if obj is None:
        return notes + ["fallback: model reply was not a JSON object"]
    lines = split_window(window)
    you_lines = [(s, t) for s, t in lines if s == "you"]
    quoted = set()
    evidence = obj.get("evidence")
    for item in evidence if isinstance(evidence, list) else []:
        if not isinstance(item, dict):
            notes.append("dropped  (evidence item is not an object)")
            continue
        tactic, quote = item.get("tactic"), item.get("quote")
        label = f"{str(tactic):<21} {str(item.get('strength', '-')):<6}"
        if tactic not in TACTICS:
            verdict = "dropped: unknown tactic"
        elif not isinstance(quote, str) or not quote.strip():
            verdict = "dropped: no quote"
        elif find_in_caller(quote, lines):
            verdict = "kept"
            quoted.add(tactic)
        elif find_in_caller(quote, [("caller", t) for _, t in you_lines]):
            verdict = "dropped: said by you, not the caller"
        else:
            verdict = "dropped: not word-for-word in a caller line"
        notes.append(f"{label} {verdict:<44} {_short(quote) if isinstance(quote, str) else ''}")
    listed = obj.get("tactics")
    for tactic in listed if isinstance(listed, list) else []:
        if tactic in TACTICS and tactic not in quoted and not any(
                isinstance(i, dict) and i.get("tactic") == tactic
                for i in (evidence if isinstance(evidence, list) else [])):
            notes.append(f"{tactic:<21} {'-':<6} dropped: listed in tactics but no evidence quote")
    if not notes:
        notes.append("model reported no evidence")
    if isinstance(obj.get("reason"), str) and obj["reason"].strip():
        notes.append(f"reason: {_short(obj['reason'])}")
    return notes


def evaluate(paths: Iterable[Path], *, post: Post | None = None,
             verbose: bool = False) -> tuple[list[dict], dict]:
    """Return beat rows and aggregate counts. `post` lets tests stay offline."""
    rows: list[dict] = []
    rules = load_rules()
    send, seen = _recording(post)
    for path in paths:
        headers, lines = read_script(path)
        expected = [set(item.strip().split("|")) for item in headers["expect"].split(",")]
        beat = 0
        window: list[str] = []
        for speaker, speech in lines:
            window.append(f"{speaker}: {speech}")
            if speaker != "caller":
                continue
            beat += 1
            if beat > len(expected):
                raise ValueError(f"expect count too short: {path.name}")
            text = "\n".join(window)
            start = time.monotonic()
            result = check(text, rules, post=send)
            elapsed_ms = (time.monotonic() - start) * 1000
            row = {
                "script": headers["id"], "kind": headers.get("kind", ""),
                "giveaway": int(headers.get("giveaway", "0")), "beat": beat,
                "expect": "|".join(sorted(expected[beat - 1])),
                "got": result["risk"], "conf": result.get("confidence", 0.0),
                "tactics": ",".join(result["tactics"]), "ms": elapsed_ms,
                "source": result.get("source", "model"),
                "ok": result["risk"] in expected[beat - 1]
                      and result.get("source") not in ("fallback", "fast"),
            }
            if verbose:
                row["notes"] = diagnose(seen, text, elapsed_ms)
            rows.append(row)
        if beat != len(expected):
            raise ValueError(f"expect count too long: {path.name}")
    scam_giveaways = [r for r in rows if r["kind"] == "scam"
                      and r["beat"] == r["giveaway"]]
    twins = [r for r in rows if r["kind"] == "twin"]
    latencies = sorted(r["ms"] for r in rows)
    p95 = latencies[max(0, math.ceil(0.95 * len(latencies)) - 1)] if latencies else 0.0
    summary = {
        "beats": len(rows), "passed": sum(r["ok"] for r in rows),
        "scam_giveaways": len(scam_giveaways),
        "scam_danger": sum(r["got"] == "danger" for r in scam_giveaways),
        "twin_beats": len(twins), "twin_danger": sum(r["got"] == "danger" for r in twins),
        "twin_low": sum(r["got"] == "low" for r in twins), "p95_ms": p95,
    }
    return rows, summary


def print_table(rows: list[dict], summary: dict) -> None:
    print(f"{'script':<22} {'beat':>4}  {'expect':<12} {'got':<7} {'conf':>4}  "
          f"{'tactics':<45} {'ms':>5}  ok")
    for row in rows:
        failed = f" ({row['source']})" if row["source"] in ("fallback", "fast") else ""
        print(f"{row['script']:<22} {row['beat']:>4}  {row['expect']:<12} "
              f"{row['got']:<7} {row['conf']:>4.2f}  {row['tactics'][:45]:<45} "
              f"{row['ms']:>5.0f}  {'✔' if row['ok'] else 'FAIL'}"
              f"{failed}")
        for note in row.get("notes", []):
            print(f"    {note}")
    print(f"SUMMARY beats {summary['passed']}/{summary['beats']} pass · "
          f"scam giveaways danger {summary['scam_danger']}/{summary['scam_giveaways']} · "
          f"twins danger {summary['twin_danger']}/{summary['twin_beats']} · "
          f"twins low {summary['twin_low']}/{summary['twin_beats']} · "
          f"p95 latency {summary['p95_ms'] / 1000:.1f} s")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate detection against local Ollama")
    parser.add_argument("--scripts", type=Path, default=DEFAULT_SCRIPTS,
                        help="script directory (default: tests/detection/scripts)")
    parser.add_argument("--script", action="append", help="script ID; may be repeated")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show each evidence quote (<= 80 chars) and why it was kept or dropped")
    args = parser.parse_args(argv)
    paths = sorted(args.scripts.glob("*.txt"))
    if args.script:
        paths = [path for path in paths if path.stem in args.script]
    if not paths:
        parser.error("no matching scripts")
    try:
        rows, summary = evaluate(paths, verbose=args.verbose)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"eval error: {exc}\n")
    print_table(rows, summary)
    return 0 if summary["passed"] == summary["beats"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
