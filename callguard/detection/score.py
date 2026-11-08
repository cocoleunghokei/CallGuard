"""Deterministic confidence and risk from caller evidence (prd section 6)."""
from __future__ import annotations

from math import prod
from typing import Iterable

from callguard.shared.contracts import SAFE_SIGNALS, TACTICS, Evidence, Risk

WEIGHT = {
    "authority": 0.35, "secrecy": 0.45, "urgency": 0.15, "threat": 0.40,
    "credential_request": 0.60, "bank_change": 0.55, "bypass_approval": 0.50,
    "payment_request": 0.55, "remote_access": 0.60,
    "personal_data_request": 0.50, "inside_knowledge": 0.20,
}
STRENGTH = {"clear": 0.9, "hint": 0.5, "phrase": 0.6}
COMBOS = (
    ("authority", "secrecy"), ("authority", "threat"),
    ("bank_change", "urgency"), ("credential_request", "authority"),
    ("credential_request", "urgency"), ("bypass_approval", "urgency"),
    ("payment_request", "threat"), ("secrecy", "payment_request"),
)
ASK_TACTICS = frozenset({
    "credential_request", "bank_change", "bypass_approval", "payment_request",
    "remote_access", "personal_data_request",
})


def best_strength_per_tactic(evidence: Iterable[Evidence]) -> dict[str, float]:
    """Ignore employee speech and unknown evidence; reward phrase/model agreement."""
    found: dict[str, set[str]] = {}
    for item in evidence:
        if not isinstance(item, dict) or item.get("speaker", "caller") != "caller":
            continue
        tactic, strength = item.get("tactic"), item.get("strength")
        if tactic in TACTICS and strength in STRENGTH:
            found.setdefault(tactic, set()).add(strength)
    result = {}
    for tactic, strengths in found.items():
        model_value = max((STRENGTH[s] for s in strengths if s != "phrase"), default=0.0)
        if model_value and "phrase" in strengths:
            result[tactic] = min(0.95, model_value + 0.05)
        else:
            result[tactic] = model_value or STRENGTH["phrase"]
    return result


def score(evidence: Iterable[Evidence], rules_broken: Iterable[str] = (),
          safe_signals: Iterable[str] = (), *, model_failed: bool = False) -> tuple[float, Risk]:
    """Return (confidence, risk), applying G1-G6 after the score formula."""
    items = list(evidence)
    strengths = best_strength_per_tactic(items)
    if model_failed and not strengths:  # G5
        return 0.0, "low"
    tactics = set(strengths)
    rules = set(rules_broken)
    safe = set(safe_signals) & set(SAFE_SIGNALS)
    base = 1 - prod(1 - WEIGHT[t] * c for t, c in strengths.items())
    combo = min(0.25, 0.15 * sum(a in tactics and b in tactics for a, b in COMBOS))
    rule_bonus = min(0.30, 0.15 * len(rules))
    safe_discount = min(0.30, 0.15 * len(safe))
    confidence = max(0.0, min(1.0, base + combo + rule_bonus - safe_discount))

    only_soft = bool(tactics) and tactics <= {"urgency", "authority"}  # G1
    has_teeth = bool(tactics & ASK_TACTICS or rules or
                     {"authority", "secrecy", "threat"} <= tactics)  # G2
    caller_items = [item for item in items if isinstance(item, dict)
                    and item.get("speaker", "caller") == "caller"
                    and item.get("tactic") in tactics]
    phrase_only = bool(caller_items) and all(item.get("strength") == "phrase"
                                              for item in caller_items)  # G3
    if confidence >= 0.75 and (only_soft or not has_teeth or phrase_only):
        confidence = 0.74
    # G6 (Coco, Sun): a CLEAR ask that breaks an enabled firm rule is danger on its
    # own ("we never change bank details by phone"). Hints and safe signals don't
    # count, so a misread on a real bank call (B3) stays below danger.
    clear_ask = any(item.get("tactic") in ASK_TACTICS and item.get("strength") == "clear"
                    for item in caller_items)
    if clear_ask and rules and not safe:
        confidence = max(confidence, 0.75)
    risk: Risk = "danger" if confidence >= 0.75 else "watch" if confidence >= 0.40 else "low"
    return confidence, risk
