"""DET-3: turn the model's raw reply into clean, checked fields (prd C5).

`parse()` never raises. It returns None when the reply is not a JSON object
at all (check() then falls back), otherwise a dict with exactly:
  tactics, evidence, claimed_identity, safe_signals, reason, next_step

Hallucination guard: every evidence quote must appear in a CALLER line of the
window (G4: `you` lines never count). Quotes that don't are dropped, and a
tactic only survives if at least one of its quotes does. The quote returned is
the window's own text, so it is verbatim even if the model changed case.
The model's own `risk`, `confidence` and `rules_broken` are ignored: score.py
and rules.py compute those.
"""
from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from typing import Any, Iterable

from callguard.shared.contracts import SAFE_SIGNALS, TACTICS

MAX_QUOTE = 80
MAX_IDENTITY = 60
MAX_SENTENCE_WORDS = 25  # prompt asks for 20; allow a little slack, then cut
MAX_SENTENCE_CHARS = 160
# prd §9.3: never "this is fraud" or "scammer". "fraud department" (B3) is fine.
BANNED_WORDS = re.compile(
    r"\b(scam\w*|fraudulent|fraudster\w*|(?:is|are|be|looks like|likely|definitely) (?:a |an )?fraud)\b", re.I)
_NULLS = {"", "null", "none", "unknown", "n/a", "na", "-"}
_STRENGTHS = {"clear", "hint"}

Line = tuple[str, str]  # (speaker, text)


# --- window ------------------------------------------------------------------

def split_window(window: Any) -> list[Line]:
    """Accept "speaker: text" lines (str), TranscriptChunk dicts, or (speaker, text) pairs."""
    lines: list[Line] = []
    if isinstance(window, str):
        items: Iterable[Any] = window.splitlines()
    elif isinstance(window, (list, tuple)):
        items = window
    else:
        return lines
    for item in items:
        speaker = text = None
        if isinstance(item, str):
            speaker, sep, text = item.partition(":")
            if not sep:
                continue
        elif isinstance(item, dict):
            speaker, text = item.get("speaker"), item.get("text")
        elif isinstance(item, (list, tuple)) and len(item) == 2:
            speaker, text = item
        if isinstance(speaker, str) and isinstance(text, str):
            speaker = speaker.strip().lower()
            if speaker in ("caller", "you") and text.strip():
                if lines and lines[-1][0] == speaker:
                    # Live audio cuts speech into ~3 s chunks mid-sentence; join a
                    # speaker's consecutive chunks so quotes can span the cut.
                    lines[-1] = (speaker, f"{lines[-1][1]} {text.strip()}")
                else:
                    lines.append((speaker, text.strip()))
    return lines


def window_text(window: Any) -> str:
    """The window as the model sees it: one "speaker: text" line per utterance."""
    return "\n".join(f"{s}: {t}" for s, t in split_window(window))


# --- verbatim quote search ---------------------------------------------------

_QUOTE_MAP = str.maketrans({"’": "'", "‘": "'", "“": '"', "”": '"'})


def _norm_with_index(text: str) -> tuple[str, list[int]]:
    """Lowercase, straighten quotes, collapse whitespace; keep a map back to `text`."""
    out, idx = [], []
    prev_space = True
    for i, ch in enumerate(text.translate(_QUOTE_MAP)):
        if ch.isspace():
            if prev_space:
                continue
            ch, prev_space = " ", True
        else:
            prev_space = False
        out.append(ch.lower())
        idx.append(i)
    while out and out[-1] == " ":
        out.pop()
        idx.pop()
    return "".join(out), idx


def _strip_quote(q: str) -> str:
    return q.strip().strip("\"'“”‘’`").strip().rstrip(".,;:!?…").strip()


def find_in_caller(quote: str, lines: list[Line]) -> str | None:
    """Return the window's own text for `quote` if it appears in a caller line, else None.

    Exact (case/whitespace-insensitive) match first; then a word-level near match
    that tolerates live mishearings (see `_near_match`).
    """
    q = _strip_quote(quote)
    if not q:
        return None
    nq, _ = _norm_with_index(q)
    callers = [text for speaker, text in lines if speaker == "caller"]
    for text in callers:
        nt, idx = _norm_with_index(text)
        at = nt.find(nq)
        if at >= 0:
            return text[idx[at]: idx[at + len(nq) - 1] + 1]
    for text in callers:
        found = _near_match(q, text)
        if found:
            return found
    return None


# --- near match (live transcripts) ---------------------------------------------
# Whisper drops or adds small words ("as a / The police officer"), splits words
# ("has been issued" -> "has an issue") and the model tidies up what it quotes
# ("I'm" for "I am"). A quote still counts when its words line up with a caller
# line after ignoring filler and contractions, with a few word edits allowed:
# 0 for quotes under 5 words (after filler is dropped), 1 for 5-7, 2 for 8+. The kept quote is
# always the caller line's own text, so evidence stays word-for-word.

_WORD = re.compile(r"[a-z0-9]+(?:'[a-z]+)?")
_FILLER = frozenset({"a", "an", "the", "uh", "um", "er", "ah", "oh"})
_CONTRACTIONS = {"can't": ("can", "not"), "won't": ("will", "not"), "i'm": ("i", "am")}
_SUFFIXES = {"n't": "not", "'re": "are", "'ll": "will", "'ve": "have"}


def _words(text: str) -> list[tuple[str, int, int]]:
    """(word, start, end) for each normalised word of `text`; offsets point into `text`."""
    out: list[tuple[str, int, int]] = []
    for m in _WORD.finditer(text.translate(_QUOTE_MAP).lower()):
        w, s, e = m.group(), m.start(), m.end()
        if w in _CONTRACTIONS:
            parts: tuple[str, ...] = _CONTRACTIONS[w]
        else:
            parts = (w,)
            for suf, full in _SUFFIXES.items():
                if w.endswith(suf) and len(w) > len(suf):
                    parts = (w[: -len(suf)], full)
                    break
        out.extend((p, s, e) for p in parts if p not in _FILLER)
    return out


def _same_word(a: str, b: str) -> bool:
    if a == b:
        return True
    if min(len(a), len(b)) < 4:
        return False
    return SequenceMatcher(None, a, b).ratio() >= 0.8  # issued/issue, laundering/launderin


def _near_match(quote: str, text: str) -> str | None:
    q = [w for w, _, _ in _words(quote)]
    t = _words(text)
    if not q or not t:
        return None
    budget = 0 if len(q) < 5 else 1 if len(q) < 8 else 2
    # Approximate substring match on words (edit distance, free start in `t`).
    # prev[j] = (cost, start index in t) for q[:i] ending just before t[j].
    prev = [(0, j) for j in range(len(t) + 1)]
    for i in range(1, len(q) + 1):
        cur = [(i, 0)]
        for j in range(1, len(t) + 1):
            sub = prev[j - 1][0] + (0 if _same_word(q[i - 1], t[j - 1][0]) else 1)
            options = [(sub, prev[j - 1][1]), (prev[j][0] + 1, prev[j][1]),
                       (cur[j - 1][0] + 1, cur[j - 1][1])]
            cur.append(min(options))
        prev = cur
    cost, end = min((c, j) for j, (c, _) in enumerate(prev) if j > 0)
    start = prev[end][1]
    if cost > budget or end <= start:
        return None
    return text[t[start][1]: t[end - 1][2]]


def _cut(text: str, limit: int) -> str:
    if len(text) <= limit:
        return text
    cut = text[:limit]
    return cut[: cut.rfind(" ")] if " " in cut else cut


# --- fields ------------------------------------------------------------------

def _sentence(value: Any) -> str:
    """One short plain sentence, or "" if missing or if it breaks the copy rules."""
    if not isinstance(value, str):
        return ""
    s = re.sub(r"\s+", " ", value).strip()
    if not s or BANNED_WORDS.search(s):
        return ""
    words = s.split(" ")
    if len(words) > MAX_SENTENCE_WORDS:
        s = " ".join(words[:MAX_SENTENCE_WORDS]).rstrip(",;:") + "."
    return _cut(s, MAX_SENTENCE_CHARS)


def _identity(value: Any) -> str | None:
    if not isinstance(value, str):
        return None
    s = re.sub(r"\s+", " ", value).strip().strip("\"'")
    if s.lower() in _NULLS:
        return None
    return _cut(s, MAX_IDENTITY) or None


def _evidence(value: Any, lines: list[Line]) -> list[dict]:
    best: dict[str, dict] = {}
    for item in value if isinstance(value, list) else []:
        if not isinstance(item, dict):
            continue
        tactic, quote = item.get("tactic"), item.get("quote")
        if tactic not in TACTICS or not isinstance(quote, str):
            continue
        found = find_in_caller(quote, lines)
        if not found:
            continue  # hallucinated, paraphrased, or said by `you`
        strength = item.get("strength")
        strength = strength if strength in _STRENGTHS else "hint"
        ev = {"tactic": tactic, "quote": _cut(found, MAX_QUOTE), "strength": strength, "speaker": "caller"}
        if tactic not in best or (strength == "clear" and best[tactic]["strength"] != "clear"):
            best[tactic] = ev
    return list(best.values())


def _load_object(raw: Any) -> dict | None:
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, bytes):
        raw = raw.decode("utf-8", "replace")
    if not isinstance(raw, str):
        return None
    try:
        obj = json.loads(raw)
    except (ValueError, RecursionError):
        start, end = raw.find("{"), raw.rfind("}")
        if start < 0 or end <= start:
            return None
        try:
            obj = json.loads(raw[start: end + 1])
        except (ValueError, RecursionError):
            return None
    return obj if isinstance(obj, dict) else None


def parse(raw: Any, window: Any) -> dict | None:
    """Validate a model reply against the window. Never raises."""
    try:
        obj = _load_object(raw)
        if obj is None:
            return None
        lines = split_window(window)
        evidence = _evidence(obj.get("evidence"), lines)
        signals = obj.get("safe_signals")
        return {
            "tactics": [e["tactic"] for e in evidence],
            "evidence": evidence,
            "claimed_identity": _identity(obj.get("claimed_identity")),
            "safe_signals": list(dict.fromkeys(
                s for s in (signals if isinstance(signals, list) else []) if s in SAFE_SIGNALS)),
            "reason": _sentence(obj.get("reason")),
            "next_step": _sentence(obj.get("next_step")),
        }
    except Exception:  # belt and braces: parse must never take the pipeline down
        return None
