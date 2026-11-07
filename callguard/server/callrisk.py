"""SRV-7: call-level risk smoothing (C10, prd §6.7, §10.5).

Per-window checks jump around as the 30 s window slides; the UI is sent the
CALL risk instead:
- rises immediately;
- `danger` is sticky until mark-safe or the call ends (hang up / colleague are
  recorded, but the meter stays red);
- `watch` drops to `low` after 3 consecutive `low` checks;
- while danger, the check shown is the highest-confidence one (its tactics and
  evidence), newest wins a tie;
- after mark-safe, only an ask tactic not seen before in this call brings
  danger back; anything else is capped at `watch`.
"""
from __future__ import annotations

from callguard.shared.contracts import ScamCheck

ORDER = {"low": 0, "watch": 1, "danger": 2}
ASK_TACTICS = frozenset({
    "credential_request", "bank_change", "bypass_approval",
    "payment_request", "remote_access", "personal_data_request",
})
DECAY_LOW_CHECKS = 3


def asks(check: ScamCheck) -> set[str]:
    return ASK_TACTICS.intersection(check.get("tactics") or [])


def _conf(check: ScamCheck | None) -> float:
    if not check:
        return -1.0
    c = check.get("confidence")
    return float(c) if isinstance(c, (int, float)) else -1.0


class CallRisk:
    def __init__(self) -> None:
        self.reset()

    def reset(self) -> None:
        self.risk = "low"
        self.shown: ScamCheck | None = None
        self.low_streak = 0
        self.marked_safe = False
        self.acted: list[str] = []
        self.seen_asks: set[str] = set()

    def _show(self, check: ScamCheck, risk: str) -> ScamCheck:
        self.risk = risk
        self.shown = {**check, "risk": risk}  # type: ignore[typeddict-item]
        return self.shown

    def update(self, check: ScamCheck) -> ScamCheck:
        """Feed one window check, get the call-level check to send to the UI."""
        raw = check.get("risk", "low")
        if raw not in ORDER:
            raw = "low"
        new_asks = asks(check) - self.seen_asks
        if raw == "danger":
            self.seen_asks |= asks(check)

        if raw == "danger" and self.marked_safe and not new_asks:
            raw = "watch"  # no re-nagging after mark-safe without a new ask
        if raw == "danger" and new_asks:
            self.marked_safe = False

        if self.risk == "danger":
            if raw == "danger" and _conf(check) >= _conf(self.shown):
                return self._show(check, "danger")
            return self.shown  # type: ignore[return-value]

        if raw == "low":
            self.low_streak += 1
            if self.risk == "watch" and self.low_streak < DECAY_LOW_CHECKS:
                return self.shown  # type: ignore[return-value]
            return self._show(check, "low")

        self.low_streak = 0
        return self._show(check, raw)

    def act(self, how: str) -> ScamCheck | None:
        """User took a way out: hang_up | colleague | mark_safe."""
        self.acted.append(how)
        if how != "mark_safe":
            return self.shown
        self.marked_safe = True
        self.low_streak = 0
        base = self.shown or {"tactics": [], "claimed_identity": None, "rules_broken": [],
                              "reason": "", "next_step": ""}
        return self._show({**base, "reason": "You marked this call as safe.",  # type: ignore[typeddict-item]
                           "next_step": ""}, "low")
