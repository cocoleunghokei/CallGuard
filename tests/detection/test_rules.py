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
