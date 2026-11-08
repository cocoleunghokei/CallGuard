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


def test_a_broken_rule_alone_shows_watch():
    assert score([], ["custom_gift_cards"]) == (0.40, "watch")
    conf, risk = score([ev("urgency")], ["r"])  # 0.14 + 0.15 is still under the floor
    assert risk == "watch" and conf == 0.40


def test_rule_floor_is_only_a_floor():
    assert score([ev("urgency")], [], [])[1] == "low", "no rule, no floor"
    conf, risk = score([], ["a", "b"])  # two cue-only rules: still Watch, never Danger
    assert (conf, risk) == (0.40, "watch")
    assert score([ev("authority"), ev("threat")], ["r"])[1] == "danger", "higher scores are untouched"
