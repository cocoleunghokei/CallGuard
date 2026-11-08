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


# --- G6: a clear ask that breaks a firm rule is danger on its own (Coco, Sun) ---

def _e(tactic, strength):
    return {"tactic": tactic, "quote": "q", "strength": strength, "speaker": "caller"}


def test_g6_clear_ask_breaking_a_rule_is_danger():
    # Live eval S2 beat 2: bank_change clear + no_bank_changes_by_phone was 0.65 watch.
    conf, risk = score([_e("bank_change", "clear")], ["no_bank_changes_by_phone"])
    assert risk == "danger" and conf == 0.75


def test_g6_hinted_ask_with_rule_stays_below_danger():
    # Live eval B3 beat 2: a misread `payment_request` hint broke the government rule.
    conf, risk = score([_e("authority", "clear"), _e("payment_request", "hint")],
                       ["government_never_calls_for_payment_or_bank_details"])
    assert risk != "danger"


def test_g6_safe_signal_blocks_the_floor():
    _, risk = score([_e("bank_change", "clear")], ["no_bank_changes_by_phone"],
                    ["callback_known_number"])
    assert risk != "danger"


def test_g6_needs_a_broken_rule():
    _, risk = score([_e("bank_change", "clear")], [])
    assert risk != "danger"


def test_g6_ignores_employee_speech():
    item = dict(_e("bank_change", "clear"), speaker="you")
    _, risk = score([item], ["no_bank_changes_by_phone"])
    assert risk == "low"
