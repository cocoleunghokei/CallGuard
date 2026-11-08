"""DET-6: reproduce every prd section 6.6 row and guards G1-G5."""
import pytest

from callguard.detection.score import ASK_TACTICS, WEIGHT, score
from callguard.shared.contracts import TACTICS


def ev(tactic, strength="clear", speaker="caller"):
    return {"tactic": tactic, "quote": "caller words", "strength": strength,
            "speaker": speaker}


@pytest.mark.parametrize("name,evidence,rules,safe,want,risk", [
    ("S1 beat 1", [ev("authority")], [], [], 0.31, "low"),
    ("S1 beat 2", [ev("authority"), ev("threat")], [], [], 0.71, "watch"),
    ("S1 beat 3", [ev("authority"), ev("threat"), ev("secrecy")], [], [], 0.99, "danger"),
    ("S2 beat 2", [ev("bank_change"), ev("urgency")], ["bank"], [], 0.86, "danger"),
    ("S3 beat 2", [ev("credential_request"), ev("authority", "hint"), ev("urgency")],
     ["it"], [], 1.00, "danger"),
    ("S4 beat 2", [ev("payment_request"), ev("urgency"), ev("bypass_approval"),
                    ev("secrecy", "hint")], ["wire"], [], 1.00, "danger"),
    ("B2", [ev("urgency")], [], [], 0.14, "low"),
    ("B3", [ev("authority")], [], ["callback_known_number"], 0.16, "low"),
    ("B4", [ev("authority", "hint")], [], ["no_money_or_data_asked"], 0.03, "low"),
    ("B5", [ev("payment_request")], [], ["follows_normal_approval"], 0.35, "low"),
])
def test_prd_6_6(name, evidence, rules, safe, want, risk):
    got, level = score(evidence, rules, safe)
    assert round(got, 2) == want, name
    assert level == risk, name


def test_weight_catalog_covers_contract():
    assert set(WEIGHT) == set(TACTICS)
    assert ASK_TACTICS <= set(TACTICS)


def test_g2_no_ask_rule_or_strong_trio_caps_danger():
    evidence = [ev("authority"), ev("secrecy"), ev("inside_knowledge"), ev("urgency")]
    assert score(evidence) == (0.74, "watch")


def test_g3_phrase_only_cannot_reach_danger():
    evidence = [ev("bank_change", "phrase"), ev("urgency", "phrase")]
    assert score(evidence, ["bank", "other"]) == (0.74, "watch")


def test_g4_employee_words_are_ignored():
    assert score([ev("credential_request", speaker="you")]) == (0.0, "low")


def test_g5_model_failure_without_phrase_evidence():
    assert score([], model_failed=True) == (0.0, "low")


def test_phrase_and_model_agreement_adds_five_points():
    evidence = [ev("authority", "clear"), ev("authority", "phrase")]
    assert round(score(evidence)[0], 3) == 0.333


def test_two_safe_signals_are_capped_at_thirty_points():
    assert score([ev("authority")], safe_signals=["callback_known_number",
                                                 "asks_in_writing"])[0] < 0.02


@pytest.mark.parametrize("name,evidence,rules,safe,risk", [
    # Live Mac misses (Sun): a clear ask plus a broken firm rule, nothing else.
    ("S3 beat 2 live", [ev("credential_request")], ["it"], [], "danger"),
    ("S2 beat 2 live", [ev("bank_change")], ["bank"], [], "danger"),
    ("S4 beat 2 live", [ev("bypass_approval")], ["wire"], [], "danger"),
    # G6 does not fire without each of its conditions.
    ("ask is only a hint", [ev("credential_request", "hint")], ["it"], [], "watch"),
    ("no rule broken", [ev("credential_request")], [], [], "watch"),
    ("caller gave a safe signal", [ev("bank_change")], ["bank"], ["asks_in_writing"], "watch"),
    ("keyword phrase only", [ev("bank_change", "phrase")], ["bank"], [], "watch"),
    ("rule but no ask", [ev("secrecy")], ["secret"], [], "watch"),
])
def test_g6_clear_ask_breaking_a_rule(name, evidence, rules, safe, risk):
    assert score(evidence, rules, safe)[1] == risk, name
