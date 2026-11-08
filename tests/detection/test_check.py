"""DET-7: the integrated check uses a fake local-model transport."""
import json

from callguard.detection import check
from callguard.detection.ollama_client import TIMEOUT_S
from callguard.detection.rules import load_rules


def post_for(content):
    def post(url, payload, timeout=None):
        assert url == "http://localhost:11434/api/chat"
        assert timeout == TIMEOUT_S
        return {"message": {"content": content}}
    return post


def reply(evidence, safe=(), identity=None):
    return json.dumps({
        "tactics": [item["tactic"] for item in evidence], "evidence": evidence,
        "claimed_identity": identity, "safe_signals": list(safe),
        "reason": "The caller made a request that needs verification.",
        "next_step": "Hang up and call back on a known number.",
    })


def ev(tactic, quote, strength="clear"):
    return {"tactic": tactic, "quote": quote, "strength": strength}


def test_rule_and_score_from_caller_only_model_evidence():
    window = "caller: We've switched banks, so Friday's payment needs to go to our new account.\nyou: Okay."
    data = reply([ev("bank_change", "We've switched banks"),
                  ev("urgency", "Friday's payment")])
    result = check(window, load_rules(), post=post_for(data))
    assert result["source"] == "model"
    assert result["risk"] == "danger"
    assert round(result["confidence"], 2) == 0.86
    assert result["rules_broken"] == ["no_bank_changes_by_phone"]
    assert result["tactics"] == ["bank_change", "urgency"]


def test_known_callback_keeps_bank_call_low():
    window = "caller: This is Chase. Hang up and call the number on the back of your card."
    data = reply([ev("authority", "This is Chase")], ["callback_known_number"], "Chase")
    result = check(window, load_rules(), post=post_for(data))
    assert result["risk"] == "low"
    assert round(result["confidence"], 2) == 0.16
    assert result["claimed_identity"] == "Chase"


def test_employee_words_cannot_raise_risk_or_break_rules():
    window = "caller: This is a birthday surprise.\nyou: Don't tell colleagues."
    data = reply([ev("secrecy", "Don't tell colleagues")])
    result = check(window, load_rules(), post=post_for(data))
    assert result["tactics"] == []
    assert result["rules_broken"] == []
    assert result["risk"] == "low"


def test_model_exception_returns_valid_low_failure():
    def failing(*args, **kwargs):
        raise TimeoutError("private caller text")

    result = check("caller: Read me the code.", load_rules(), post=failing)
    assert result["source"] == "fallback"
    assert result["risk"] == "low" and result["confidence"] == 0.0
    assert "failed" in result["reason"]
    assert "private caller text" not in str(result)


def test_bad_json_returns_failure_not_exception():
    result = check("caller: Hello.", load_rules(), post=post_for("no json"))
    assert result["source"] == "fallback"
    assert "failed" in result["reason"]


def test_empty_model_object_returns_failure():
    result = check("caller: Hello.", load_rules(), post=post_for("{}"))
    assert result["source"] == "fallback"


def test_empty_window_does_not_call_model():
    def no_call(*args, **kwargs):
        raise AssertionError("must not call")

    assert check("you: Hello.", load_rules(), post=no_call)["risk"] == "low"
