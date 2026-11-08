"""DET-4: rules.json loads, and each P0 rule fires (and stays quiet) as prd §8 says."""
import json

import pytest

from callguard.detection.rules import load_rules, match_rules
from callguard.shared.contracts import TACTICS

RULES = load_rules()
P0_IDS = [
    "no_bank_changes_by_phone",
    "it_never_asks_for_codes",
    "wires_need_two_approvals",
    "government_never_calls_for_payment_or_bank_details",
    "never_keep_calls_secret",
]


def test_shipped_rules_are_the_p0_set_and_valid():
    assert [r["id"] for r in RULES] == P0_IDS
    for r in RULES:
        assert 1 <= len(r["text"]) <= 200
        assert r["tactics"] and set(r["tactics"]) <= set(TACTICS)
        assert set(r.get("requires", [])) <= set(TACTICS)
        assert len(r.get("keywords", [])) <= 10
        assert all(len(k) <= 40 for k in r.get("keywords", []))


def test_no_tactics_no_text_nothing_broken():
    assert match_rules([], RULES) == []
    assert match_rules([], RULES, "Hi, how was your weekend?") == []


# --- one block per rule -------------------------------------------------------

def test_no_bank_changes_by_phone():
    assert match_rules(["bank_change"], RULES) == ["no_bank_changes_by_phone"]
    # keyword alone (S2 beat 2), even if the model missed the tactic
    assert match_rules([], RULES, "Friday's payment needs to go to our new account.") == ["no_bank_changes_by_phone"]
    # B1: invoice question, no bank change
    assert match_rules([], RULES, "Nothing changes on the payment side, thanks!") == []


def test_it_never_asks_for_codes():
    assert match_rules(["credential_request"], RULES) == ["it_never_asks_for_codes"]
    assert match_rules([], RULES, "OK, read me the code now.") == ["it_never_asks_for_codes"]
    # B4: real IT warns about codes; must not break the rule
    assert match_rules(["authority"], RULES, "Never share your MFA code with anyone, including us.") == []


def test_wires_need_two_approvals():
    assert match_rules(["bypass_approval"], RULES) == ["wires_need_two_approvals"]
    assert match_rules([], RULES, "Skip the second sign-off, I'll approve it when I land.") == ["wires_need_two_approvals"]
    # B5: a wire through the normal process does not break it (prd §6.6: rules 0)
    assert match_rules(["payment_request"], RULES, "Put it through the normal two approvals.") == []


@pytest.mark.parametrize("ask", ["payment_request", "bank_change", "personal_data_request"])
def test_government_rule_needs_authority(ask):
    with_authority = match_rules(["authority", ask], RULES)
    assert "government_never_calls_for_payment_or_bank_details" in with_authority
    # a vendor asking for a bank change is not the government rule (prd §8)
    assert "government_never_calls_for_payment_or_bank_details" not in match_rules([ask], RULES)


def test_government_rule_authority_alone_is_not_enough():
    assert match_rules(["authority"], RULES) == []


def test_never_keep_calls_secret():
    assert match_rules(["secrecy"], RULES) == ["never_keep_calls_secret"]
    assert match_rules([], RULES, "Do not tell your colleagues or your firm.") == ["never_keep_calls_secret"]
    assert match_rules([], RULES, "Keep this between us until it closes.") == ["never_keep_calls_secret"]


# --- scenario-level: what the scripts' `rules:` headers expect -----------------

def test_s1_government_full_call():
    got = match_rules(["authority", "threat", "secrecy", "bank_change"], RULES)
    # bank_change also breaks the bank-change rule; the header lists the two the catalog names
    assert {"government_never_calls_for_payment_or_bank_details", "never_keep_calls_secret"} <= set(got)


def test_s4_partner_wire_full_call():
    got = match_rules(["payment_request", "urgency", "bypass_approval", "secrecy"], RULES)
    assert set(got) == {"wires_need_two_approvals", "never_keep_calls_secret"}


def test_b7_your_own_words_do_not_count():
    # the caller's lines only; the user's "don't tell anyone" is never passed in (G4)
    caller = "Ha, of course. I'll bring the cake, can you book the conference room? Got it."
    assert match_rules([], RULES, caller) == []


# --- matcher mechanics -------------------------------------------------------

def test_keyword_match_is_case_and_apostrophe_insensitive():
    assert match_rules([], RULES, "DON’T   TELL your colleagues") == ["never_keep_calls_secret"]


def test_keywords_respect_requires():
    rules = [{"id": "r", "text": "t", "tactics": ["payment_request"], "keywords": ["gift card"], "requires": ["authority"]}]
    assert match_rules([], rules, "pay with a gift card") == []
    assert match_rules(["authority"], rules, "pay with a gift card") == ["r"]


def test_disabled_rule_never_matches():
    rules = [{"id": "r", "text": "t", "tactics": ["secrecy"], "keywords": ["secret"], "enabled": False}]
    assert match_rules(["secrecy"], rules, "it's a secret") == []


def test_order_follows_rules_file_and_no_duplicates():
    got = match_rules(["secrecy", "bank_change"], RULES, "new account, keep this between us")
    assert got == ["no_bank_changes_by_phone", "never_keep_calls_secret"]


def test_loader_skips_bad_entries_and_unknown_tactics(tmp_path):
    p = tmp_path / "rules.json"
    p.write_text(json.dumps([
        {"id": "ok", "text": "Fine.", "tactics": ["secrecy", "made_up"], "enabled": False},
        {"id": "", "text": "no id", "tactics": ["secrecy"]},
        {"id": "no_tactics", "text": "x"},
        "not a dict",
    ]))
    rules = load_rules(p)
    assert rules == [{"id": "ok", "text": "Fine.", "tactics": ["secrecy"], "enabled": False}]


# --- DET-13 (cues only): custom rules file, validation, ids --------------------

from callguard.detection.rules import load_rules_with_source, prepare_rules, validate_rules

GIFT = {"id": "custom_gift_cards", "text": "We never pay in gift cards.", "tactics": [], "keywords": ["gift card"]}


def test_shipped_rules_validate():
    assert validate_rules(RULES) == []


def test_cue_only_rule_is_valid_and_matches_on_its_phrase():
    assert validate_rules([GIFT]) == []
    assert match_rules([], [GIFT], "Pick up some Gift Cards for me") == ["custom_gift_cards"]
    assert match_rules(["urgency"], [GIFT], "Please hurry") == []


@pytest.mark.parametrize("rules,needle", [
    ("nope", "must be a list"),
    ([{**GIFT, "keywords": []}], "at least one phrase"),
    ([{**GIFT, "keywords": ["ab"]}], "3 to 40 characters"),
    ([{**GIFT, "keywords": ["x" * 41]}], "3 to 40 characters"),
    ([{**GIFT, "keywords": ["line\nbreak"]}], "one line"),
    ([{**GIFT, "keywords": [f"cue {i}" for i in range(11)]}], "at most 10 phrases"),
    ([{**GIFT, "text": ""}], "1 to 200 characters"),
    ([{**GIFT, "text": "x" * 201}], "1 to 200 characters"),
    ([{**GIFT, "tactics": ["made_up"]}], "unknown tactic"),
    ([{**GIFT, "requires": ["made_up"]}], "unknown tactic"),
    ([GIFT, GIFT], "duplicate id"),
    ([{**GIFT, "id": f"r{i}"} for i in range(31)], "At most 30 rules"),
    ([{**GIFT, "enabled": "yes"}], "on/off"),
])
def test_validate_rejects_with_a_reason(rules, needle):
    errors = validate_rules(rules)
    assert errors and any(needle in e for e in errors), errors


def test_prepare_gives_new_rules_unique_ids():
    got = prepare_rules([{"text": "Gift cards!", "keywords": ["gift card"]},
                         {"text": "Gift cards!", "keywords": ["itunes card"]},
                         {"id": "kept", "text": "Old", "keywords": ["old cue"]}])
    assert [r["id"] for r in got] == ["custom_gift_cards", "custom_gift_cards_2", "kept"]


def test_custom_file_is_preferred_and_bad_file_falls_back(tmp_path):
    p = tmp_path / "rules.json"
    assert load_rules_with_source(p) == (RULES, "default"), "missing file"
    p.write_text(json.dumps([GIFT]))
    assert load_rules_with_source(p) == ([GIFT], "custom")
    p.write_text(json.dumps([{**GIFT, "text": ""}]))
    assert load_rules_with_source(p) == (RULES, "default"), "invalid file"
    p.write_text("{not json")
    assert load_rules_with_source(p) == (RULES, "default"), "broken JSON"


def test_custom_path_from_env(monkeypatch, tmp_path):
    from callguard.detection.rules import custom_rules_path
    monkeypatch.setenv("CALLGUARD_RULES_FILE", str(tmp_path / "x.json"))
    assert custom_rules_path() == tmp_path / "x.json"
    monkeypatch.delenv("CALLGUARD_RULES_FILE")
    assert custom_rules_path().parts[-3:] == ("Application Support", "Callguard", "rules.json")
