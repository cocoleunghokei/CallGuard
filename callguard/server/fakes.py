"""Stand-ins for other lanes until they merge (guardrail 8). Used only when the
real `callguard.audio.fake_stream` / `callguard.detection.check` are missing.

fake_stream(path, speed): replays a prd §15.2 script, one 3 s chunk per line.
fake_check(window, rules): crude phrase matcher returning a valid ScamCheck
(source "fallback"). It is a demo crutch, not detection.
"""
from __future__ import annotations

import re
import time
from pathlib import Path
from typing import Iterator

from callguard.shared.contracts import Rule, ScamCheck, TranscriptChunk

CHUNK_SECONDS = 3.0


def fake_stream(path: str | Path, speed: float = 1.0) -> Iterator[TranscriptChunk]:
    t0 = time.monotonic()
    i = 0
    for raw in Path(path).read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        speaker, sep, text = line.partition(":")
        if not sep or speaker not in ("caller", "you") or not text.strip():
            raise ValueError("invalid script line")
        start = i * CHUNK_SECONDS
        i += 1
        if speed > 0:
            wait = t0 + (start + CHUNK_SECONDS) / speed - time.monotonic()
            if wait > 0:
                time.sleep(wait)
        yield {"speaker": speaker, "text": text.strip(), "start": start,
               "end": start + CHUNK_SECONDS, "language": "en"}  # type: ignore[typeddict-item]


_PHRASES: dict[str, tuple[str, ...]] = {
    "authority": ("department of", "officer", "agent", "irs", "police", "fbi", "court"),
    "threat": ("investigation", "arrest", "extradition", "warrant", "obstruction", "penalty"),
    "secrecy": ("do not tell", "don't tell", "confidential", "keep this between"),
    "urgency": ("right now", "immediately", "today", "within the hour", "urgent"),
    "inside_knowledge": ("case",),
    "bank_change": ("new account", "bank account number", "routing number", "updated bank"),
    "credential_request": ("password", "code we sent", "verification code", "one-time code"),
    "payment_request": ("wire", "gift card", "transfer the", "pay the"),
    "remote_access": ("anydesk", "teamviewer", "remote access", "install"),
    "personal_data_request": ("social security", "date of birth"),
    "bypass_approval": ("skip the approval", "no need to approve", "don't loop in"),
}
_ASKS = {"bank_change", "credential_request", "payment_request", "remote_access", "personal_data_request"}
_ORG = re.compile(r"\bfrom (?:the )?([A-Z][\w&]*(?:\s+(?:(?:of|for|and|the)\s+)*[A-Z][\w&]*){0,4})")


def fake_check(window: str, rules: list[Rule] | None = None) -> ScamCheck:
    caller = "\n".join(l.partition(":")[2] for l in window.splitlines() if l.startswith("caller:"))
    low = caller.lower()
    tactics = [t for t, ps in _PHRASES.items() if any(p in low for p in ps)]
    asks = _ASKS.intersection(tactics)
    if "secrecy" in tactics or (asks and len(tactics) >= 2):
        risk, conf = "danger", 0.99 if asks else 0.9
    elif len(tactics) >= 2 or {"threat", "urgency"} & set(tactics):
        risk, conf = "watch", 0.6
    else:
        risk, conf = "low", 0.3 if tactics else 0.05
    m = _ORG.search(caller)
    broken = [r["id"] for r in rules or [] if r.get("enabled", True) and set(r["tactics"]) & set(tactics)]
    return {
        "risk": risk, "tactics": tactics,
        "claimed_identity": m.group(1).strip() if m else None,
        "rules_broken": broken,
        "reason": "Fake check: phrase match only." if tactics else "",
        "next_step": "Verify the caller on a number you already have." if risk != "low" else "",
        "confidence": conf, "evidence": [], "safe_signals": [], "source": "fallback",
    }  # type: ignore[typeddict-item]
