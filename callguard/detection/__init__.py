"""Local scam-pattern detection entry point."""
from __future__ import annotations

from typing import Any

from callguard.shared.contracts import Rule, ScamCheck

from .ollama_client import Post, chat
from .parse import parse, split_window, window_text
from .rules import match_rules
from .score import RULE_FLOOR, score


def _fallback() -> ScamCheck:
    return {
        "risk": "low", "confidence": 0.0, "tactics": [], "evidence": [],
        "claimed_identity": None, "rules_broken": [], "safe_signals": [],
        "reason": "The local check failed; verify the caller independently.",
        "next_step": "Hang up and call back on a known number.", "source": "fallback",
    }


def _cues_only(rules: list[Rule], caller_text: str) -> ScamCheck:
    """The model didn't answer: the firm's own cue phrases still count (source "fast")."""
    try:
        broken = match_rules([], rules, caller_text)
    except Exception:
        broken = []
    if not broken:
        return _fallback()
    return {
        "risk": "watch", "confidence": RULE_FLOOR, "tactics": [], "evidence": [],
        "claimed_identity": None, "rules_broken": broken, "safe_signals": [],
        "reason": "The caller used a phrase your firm flagged.",
        "next_step": "Hang up and call back on a known number.", "source": "fast",
    }


def check(window: Any, rules: list[Rule], *, post: Post | None = None) -> ScamCheck:
    """Check caller-labelled rolling speech; never raise or expose transcript text."""
    try:
        lines = split_window(window)
        if not any(speaker == "caller" for speaker, _ in lines):
            return _fallback()
        caller_text = "\n".join(line for speaker, line in lines if speaker == "caller")
    except Exception:
        return _fallback()
    try:
        text = window_text(window)
        parsed = parse(chat(text, post=post), lines)
        if parsed is None or not any((parsed["reason"], parsed["next_step"],
                                      parsed["evidence"], parsed["safe_signals"],
                                      parsed["claimed_identity"])):
            return _cues_only(rules, caller_text)
        # `parse` only emits tactics supported by exact caller-line quotes.
        tactics = parsed["tactics"]
        broken = match_rules(tactics, rules, caller_text)
        confidence, risk = score(parsed["evidence"], broken, parsed["safe_signals"])
        return {
            "risk": risk, "confidence": confidence, "tactics": tactics,
            "evidence": parsed["evidence"], "claimed_identity": parsed["claimed_identity"],
            "rules_broken": broken, "safe_signals": parsed["safe_signals"],
            "reason": parsed["reason"] or "Verify the caller's request before acting.",
            "next_step": parsed["next_step"] or "Hang up and call back on a known number.",
            "source": "model",
        }
    except Exception:
        # Ollama, malformed inputs, and custom-rule errors all keep the pipeline alive.
        return _cues_only(rules, caller_text)
