"""Local scam-pattern detection entry point."""
from __future__ import annotations

from typing import Any

from callguard.shared.contracts import Rule, ScamCheck

from .ollama_client import Post, chat
from .parse import parse, split_window, window_text
from .phrases import phrase_evidence
from .rules import match_rules
from .score import score


def _fallback() -> ScamCheck:
    return {
        "risk": "low", "confidence": 0.0, "tactics": [], "evidence": [],
        "claimed_identity": None, "rules_broken": [], "safe_signals": [],
        "reason": "The local check failed; verify the caller independently.",
        "next_step": "Hang up and call back on a known number.", "source": "fallback",
    }


def check(window: Any, rules: list[Rule], *, post: Post | None = None) -> ScamCheck:
    """Check caller-labelled rolling speech; never raise or expose transcript text."""
    try:
        lines = split_window(window)
        if not any(speaker == "caller" for speaker, _ in lines):
            return _fallback()
        text = window_text(window)
        parsed = parse(chat(text, post=post), lines)
        if parsed is None:  # not a JSON object at all
            return _fallback()
        # A JSON object with nothing in it is the model saying "nothing seen":
        # a quiet low result, not a failure (live eval, B7 beat 1).
        # `parse` only emits tactics supported by exact caller-line quotes.
        evidence = list(parsed["evidence"])
        tactics = list(parsed["tactics"])
        for item in phrase_evidence(lines):  # urgency the model skipped
            if item["tactic"] not in tactics:
                evidence.append(item)
                tactics.append(item["tactic"])
        caller_text = "\n".join(line for speaker, line in lines if speaker == "caller")
        broken = match_rules(tactics, rules, caller_text)
        confidence, risk = score(evidence, broken, parsed["safe_signals"])
        return {
            "risk": risk, "confidence": confidence, "tactics": tactics,
            "evidence": evidence, "claimed_identity": parsed["claimed_identity"],
            "rules_broken": broken, "safe_signals": parsed["safe_signals"],
            "reason": parsed["reason"] or "Verify the caller's request before acting.",
            "next_step": parsed["next_step"] or "Hang up and call back on a known number.",
            "source": "model",
        }
    except Exception:
        # Ollama, malformed inputs, and custom-rule errors all keep the pipeline alive.
        return _fallback()
