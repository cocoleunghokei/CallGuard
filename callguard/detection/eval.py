"""Replay scenario beats against local Ollama: python -m callguard.detection.eval.

Only script IDs, risk, scores, tactics and timing are printed. Transcript text
never appears in the table or error messages.
"""
from __future__ import annotations

import argparse
import math
import time
from pathlib import Path
from typing import Iterable

from . import check
from .ollama_client import Post
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


def evaluate(paths: Iterable[Path], *, post: Post | None = None) -> tuple[list[dict], dict]:
    """Return beat rows and aggregate counts. `post` lets tests stay offline."""
    rows: list[dict] = []
    rules = load_rules()
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
            start = time.monotonic()
            result = check("\n".join(window), rules, post=post)
            elapsed_ms = (time.monotonic() - start) * 1000
            rows.append({
                "script": headers["id"], "kind": headers.get("kind", ""),
                "giveaway": int(headers.get("giveaway", "0")), "beat": beat,
                "expect": "|".join(sorted(expected[beat - 1])),
                "got": result["risk"], "conf": result.get("confidence", 0.0),
                "tactics": ",".join(result["tactics"]), "ms": elapsed_ms,
                "source": result.get("source", "model"),
                "ok": result["risk"] in expected[beat - 1]
                      and result.get("source") != "fallback",
            })
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
        print(f"{row['script']:<22} {row['beat']:>4}  {row['expect']:<12} "
              f"{row['got']:<7} {row['conf']:>4.2f}  {row['tactics'][:45]:<45} "
              f"{row['ms']:>5.0f}  {'✔' if row['ok'] else 'FAIL'}")
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
    args = parser.parse_args(argv)
    paths = sorted(args.scripts.glob("*.txt"))
    if args.script:
        paths = [path for path in paths if path.stem in args.script]
    if not paths:
        parser.error("no matching scripts")
    try:
        rows, summary = evaluate(paths)
    except (OSError, ValueError) as exc:
        parser.exit(2, f"eval error: {exc}\n")
    print_table(rows, summary)
    return 0 if summary["passed"] == summary["beats"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
