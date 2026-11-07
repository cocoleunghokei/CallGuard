"""SRV-7: rise, sticky danger, decay, max confidence, mark-safe re-nag rule."""
from callguard.server.callrisk import CallRisk


def c(risk, conf=None, tactics=(), reason=""):
    out = {"risk": risk, "tactics": list(tactics), "claimed_identity": None,
           "rules_broken": [], "reason": reason, "next_step": ""}
    if conf is not None:
        out["confidence"] = conf
    return out


def risks(cr, checks):
    return [cr.update(x)["risk"] for x in checks]


def test_rises_immediately():
    assert risks(CallRisk(), [c("low"), c("watch"), c("danger")]) == ["low", "watch", "danger"]
    assert risks(CallRisk(), [c("low"), c("danger")]) == ["low", "danger"]


def test_danger_is_sticky():
    cr = CallRisk()
    assert risks(cr, [c("danger", 0.9), c("low"), c("watch"), c("low"), c("low"), c("low")]) == ["danger"] * 6


def test_danger_shows_max_confidence_with_its_tactics():
    cr = CallRisk()
    cr.update(c("danger", 0.9, ["secrecy"]))
    cr.update(c("danger", 0.99, ["secrecy", "threat"], reason="peak"))
    out = cr.update(c("danger", 0.8, ["secrecy"], reason="lower"))
    assert out["confidence"] == 0.99 and out["reason"] == "peak" and out["tactics"] == ["secrecy", "threat"]
    out = cr.update(c("danger", 0.99, ["bank_change"], reason="newer tie"))
    assert out["reason"] == "newer tie"


def test_watch_decays_after_three_lows():
    cr = CallRisk()
    assert risks(cr, [c("watch", 0.6), c("low"), c("low"), c("low"), c("low")]) == \
        ["watch", "watch", "watch", "low", "low"]


def test_watch_decay_resets_on_non_low():
    cr = CallRisk()
    assert risks(cr, [c("watch"), c("low"), c("low"), c("watch"), c("low"), c("low"), c("low")]) == \
        ["watch"] * 6 + ["low"]


def test_hang_up_or_colleague_keeps_danger():
    cr = CallRisk()
    cr.update(c("danger", 0.99))
    assert cr.act("colleague")["risk"] == "danger"
    assert cr.update(c("low"))["risk"] == "danger"
    assert cr.acted == ["colleague"]


def test_mark_safe_lowers_and_only_a_new_ask_returns_danger():
    cr = CallRisk()
    cr.update(c("danger", 0.99, ["secrecy", "bank_change"]))
    assert cr.act("mark_safe")["risk"] == "low"
    assert cr.update(c("danger", 0.99, ["secrecy", "bank_change"]))["risk"] == "watch"  # same ask: capped
    assert cr.update(c("watch"))["risk"] == "watch"
    assert cr.update(c("danger", 1.0, ["credential_request"]))["risk"] == "danger"  # new ask


def test_mark_safe_with_no_check_yet():
    assert CallRisk().act("mark_safe")["risk"] == "low"


def test_reset_clears_everything():
    cr = CallRisk()
    cr.update(c("danger", 0.99, ["bank_change"]))
    cr.act("hang_up")
    cr.reset()
    assert (cr.risk, cr.shown, cr.acted, cr.seen_asks) == ("low", None, [], set())


def test_unknown_risk_treated_as_low():
    assert CallRisk().update(c("???"))["risk"] == "low"
