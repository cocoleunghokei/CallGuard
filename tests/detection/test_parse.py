"""DET-3: parse() validates model replies, guards against hallucinated quotes, never raises."""
import json

import pytest

from callguard.detection.parse import find_in_caller, parse, split_window, window_text
from callguard.shared.contracts import SAFE_SIGNALS, TACTICS

WINDOW = (
    "caller: Hi, this is Officer Chen from the Department of Justice.\n"
    "you: Sorry, who is this? Don't tell anyone, but I'm nervous.\n"
    "caller: This is confidential. Do not tell your colleagues or your firm, or it will be treated as obstruction."
)
KEYS = {"tactics", "evidence", "claimed_identity", "safe_signals", "reason", "next_step"}


def reply(**kw):
    base = {"tactics": [], "evidence": [], "claimed_identity": None, "safe_signals": [],
            "reason": "Caller claims to be an official.", "next_step": "Hang up and call the agency's public number."}
    base.update(kw)
    return json.dumps(base)


def ev(tactic, quote, strength="clear"):
    return {"tactic": tactic, "quote": quote, "strength": strength}


def assert_valid(out):
    assert set(out) == KEYS
    assert set(out["tactics"]) <= set(TACTICS)
    assert out["tactics"] == [e["tactic"] for e in out["evidence"]]
    for e in out["evidence"]:
        assert e["tactic"] in TACTICS and e["strength"] in {"clear", "hint"} and e["speaker"] == "caller"
        assert 0 < len(e["quote"]) <= 80 and e["quote"] in WINDOW
    assert set(out["safe_signals"]) <= set(SAFE_SIGNALS)
    assert out["claimed_identity"] is None or isinstance(out["claimed_identity"], str)
    assert isinstance(out["reason"], str) and isinstance(out["next_step"], str)


def test_good_reply():
    out = parse(reply(
        tactics=["authority", "secrecy"],
        evidence=[ev("authority", "this is Officer Chen from the Department of Justice"),
                  ev("secrecy", "Do not tell your colleagues or your firm")],
        claimed_identity="Department of Justice"), WINDOW)
    assert_valid(out)
    assert out["tactics"] == ["authority", "secrecy"]
    assert out["claimed_identity"] == "Department of Justice"


def test_hallucinated_quote_drops_the_tactic():
    out = parse(reply(tactics=["authority", "threat"],
                      evidence=[ev("authority", "Officer Chen from the Department of Justice"),
                                ev("threat", "you will be arrested tonight")]), WINDOW)
    assert out["tactics"] == ["authority"]


def test_tactic_listed_without_evidence_is_dropped():
    assert parse(reply(tactics=["urgency"]), WINDOW)["tactics"] == []


def test_quote_from_you_line_is_dropped_g4():
    out = parse(reply(evidence=[ev("secrecy", "Don't tell anyone")]), WINDOW)
    assert out["tactics"] == []


def test_quote_returned_verbatim_from_window_even_if_model_changed_case_and_spacing():
    out = parse(reply(evidence=[ev("secrecy", "  “do NOT   tell your colleagues.” ")]), WINDOW)
    assert out["evidence"][0]["quote"] == "Do not tell your colleagues"


def test_long_quote_is_cut_to_80_chars():
    long = "This is confidential. Do not tell your colleagues or your firm, or it will be treated as obstruction."
    out = parse(reply(evidence=[ev("secrecy", long)]), WINDOW)
    q = out["evidence"][0]["quote"]
    assert len(q) <= 80 and long.startswith(q)


def test_best_strength_per_tactic_and_bad_strength_becomes_hint():
    out = parse(reply(evidence=[ev("secrecy", "This is confidential", "hint"),
                                ev("secrecy", "Do not tell your colleagues", "clear"),
                                ev("authority", "Officer Chen", "phrase")]), WINDOW)
    by = {e["tactic"]: e for e in out["evidence"]}
    assert by["secrecy"]["strength"] == "clear" and by["secrecy"]["quote"] == "Do not tell your colleagues"
    assert by["authority"]["strength"] == "hint"


def test_model_risk_and_rules_are_ignored():
    out = parse(reply(risk="danger", confidence=0.99, rules_broken=["x"]), WINDOW)
    assert "risk" not in out and "confidence" not in out and "rules_broken" not in out


@pytest.mark.parametrize("bad", ["This is a scam.", "The caller is a scammer.", "This is fraud, hang up.",
                                 "Fraudulent request detected."])
def test_copy_rules_blank_banned_wording(bad):
    out = parse(reply(reason=bad, next_step=bad), WINDOW)
    assert out["reason"] == "" and out["next_step"] == ""


def test_fraud_department_is_allowed():
    out = parse(reply(reason="Caller says they are from the bank's fraud department."), WINDOW)
    assert out["reason"].startswith("Caller says")


def test_long_reason_is_cut():
    out = parse(reply(reason=" ".join(["word"] * 60)), WINDOW)
    assert len(out["reason"].split()) <= 25 and len(out["reason"]) <= 160


@pytest.mark.parametrize("value", [None, "", "null", "None", "unknown", 42, ["DOJ"], "  "])
def test_empty_identity_becomes_none(value):
    assert parse(reply(claimed_identity=value), WINDOW)["claimed_identity"] is None


def test_unknown_safe_signals_dropped_and_deduped():
    out = parse(reply(safe_signals=["callback_known_number", "vibes", "callback_known_number"]), WINDOW)
    assert out["safe_signals"] == ["callback_known_number"]


def test_json_wrapped_in_text_or_fences_is_recovered():
    raw = "Sure! ```json\n" + reply(evidence=[ev("authority", "Officer Chen")]) + "\n```"
    assert parse(raw, WINDOW)["tactics"] == ["authority"]


# --- window formats ----------------------------------------------------------

def test_window_formats_agree():
    chunks = [{"speaker": "caller", "text": "Officer Chen here.", "start": 0.0, "end": 3.0, "language": "en"},
              {"speaker": "you", "text": "Hi.", "start": 3.0, "end": 6.0, "language": "en"}]
    pairs = [("caller", "Officer Chen here."), ("you", "Hi.")]
    text = "caller: Officer Chen here.\nyou: Hi."
    assert split_window(chunks) == split_window(pairs) == split_window(text) == pairs
    assert window_text(chunks) == text


def test_window_skips_junk_lines():
    assert split_window("no speaker here\nrobot: hi\ncaller:   \ncaller: ok") == [("caller", "ok")]
    assert split_window(None) == [] and split_window(5) == []


def test_find_in_caller_ignores_you_lines():
    lines = [("you", "keep it secret"), ("caller", "hello")]
    assert find_in_caller("keep it secret", lines) is None
    assert find_in_caller("HELLO.", lines) == "hello"


# --- fuzz: 20 malformed outputs, never raises ----------------------------------

MALFORMED = [
    None,
    "",
    "not json at all",
    "{",
    "}{",
    "[1, 2, 3]",
    '"just a string"',
    "42",
    "null",
    '{"evidence": "secrecy"}',
    '{"evidence": [1, "x", null, {"tactic": "secrecy"}]}',
    '{"evidence": [{"tactic": 5, "quote": "Officer Chen"}]}',
    '{"evidence": [{"tactic": "authority", "quote": ["Officer Chen"]}]}',
    '{"evidence": [{"tactic": "mind_control", "quote": "Officer Chen", "strength": "clear"}]}',
    '{"tactics": "authority", "safe_signals": "callback_known_number", "reason": 7, "next_step": {}}',
    '{"claimed_identity": {"name": "DOJ"}, "reason": null}',
    '{"evidence": [{"tactic": "authority", "quote": "", "strength": "clear"}]}',
    "{" * 5000,
    b'{"evidence": [{"tactic": "authority", "quote": "Officer Chen", "strength": "clear"}]}',
    '{"evidence": [{"tactic": "secrecy", "quote": "\\u0000\\ud800", "strength": "clear"}]} trailing junk',
]


def test_fuzz_has_twenty_cases():
    assert len(MALFORMED) == 20


@pytest.mark.parametrize("raw", MALFORMED, ids=range(len(MALFORMED)))
@pytest.mark.parametrize("window", [WINDOW, "", None, [{"speaker": 1}], "caller: x"])
def test_fuzz_never_raises(raw, window):
    out = parse(raw, window)
    if out is not None:
        assert set(out) == KEYS
        assert set(out["tactics"]) <= set(TACTICS)
        assert set(out["safe_signals"]) <= set(SAFE_SIGNALS)
        for e in out["evidence"]:
            assert e["speaker"] == "caller" and len(e["quote"]) <= 80


def test_fuzz_non_objects_return_none():
    for raw in [None, "", "not json at all", "{", "[1, 2, 3]", '"just a string"', "42", "null"]:
        assert parse(raw, WINDOW) is None


# --- live transcripts: chunk joins + near match (Coco's live S1 run, Sun) -------

LIVE = (
    "caller: I am Officer Weng from Diminish.\n"
    "caller: of public security in Beijing.\n"
    "you: Uh, yes. Sorry, what is this?\n"
    "caller: as a\n"
    "caller: The police officer, I must tell you your name is Lee.\n"
    "caller: to a money laundering case in Sun Jin.\n"
    "caller: You are a suspect and the warrant has\n"
    "caller: an issue.\n"
    "you: I'm a lawyer. I don't do the...\n"
    "caller: We know about the cases you were\n"
    "caller: on. Officers can come to arrest."
)


def test_consecutive_chunks_of_one_speaker_are_joined():
    lines = split_window("caller: You are a suspect and\ncaller: a warrant\nyou: what\ncaller: ok")
    assert lines == [("caller", "You are a suspect and a warrant"), ("you", "what"), ("caller", "ok")]


@pytest.mark.parametrize("quote, found", [
    ("As a police officer", "as a The police officer"),
    ("You are a suspect and a warrant has been issued", "You are a suspect and the warrant has an issue"),
    ("I'm Officer Wang from the Ministry of Public Security",
     "I am Officer Weng from Diminish. of public security"),
    ("We know about the cases you work on", "We know about the cases you were on"),
])
def test_near_match_survives_live_mishearings(quote, found):
    assert find_in_caller(quote, split_window(LIVE)) == found


@pytest.mark.parametrize("quote", [
    "give me your password", "Do not tell your colleagues", "I'm a lawyer",
    "wire the money to this account today", "You are not a suspect at all, sorry",
])
def test_near_match_still_drops_what_the_caller_never_said(quote):
    assert find_in_caller(quote, split_window(LIVE)) is None


def test_live_split_scores_amber_from_caller_3():
    from callguard.detection.score import score
    out = parse(reply(evidence=[ev("authority", "As a police officer"),
                                ev("threat", "You are a suspect and a warrant has been issued")]), LIVE)
    assert out["tactics"] == ["authority", "threat"]
    assert all(e["quote"] in LIVE.replace("\ncaller: ", " ") for e in out["evidence"])
    assert score(out["evidence"])[1] == "watch"
