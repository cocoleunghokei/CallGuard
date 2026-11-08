"""DET-9: beat replay and summary without a live Ollama or transcript output."""
import io
import json
from contextlib import redirect_stdout

from callguard.detection.eval import DEFAULT_SCRIPTS, evaluate, print_table, read_script


def quiet_post(url, payload, timeout=None):
    assert url == "http://localhost:11434/api/chat"
    return {"message": {"content": (
        '{"tactics":[],"evidence":[],"claimed_identity":null,'
        '"safe_signals":[],"reason":"No request yet.",'
        '"next_step":"Verify first on a known number."}')
    }}


def test_p0_scripts_replay_each_caller_beat():
    paths = sorted(DEFAULT_SCRIPTS.glob("*.txt"))
    assert len(paths) >= 8
    for path in paths:
        headers, lines = read_script(path)
        rows, summary = evaluate([path], post=quiet_post)
        assert len(rows) == sum(speaker == "caller" for speaker, _ in lines)
        assert len(rows) == len(headers["expect"].split(","))
        assert summary["beats"] == len(rows)
        assert all(row["source"] == "model" for row in rows)


def test_printed_table_has_no_transcript_text():
    paths = [DEFAULT_SCRIPTS / "b1_vendor_invoice.txt"]
    rows, summary = evaluate(paths, post=quiet_post)
    out = io.StringIO()
    with redirect_stdout(out):
        print_table(rows, summary)
    text = out.getvalue()
    assert "SUMMARY beats 3/3 pass" in text
    assert "invoice 2210" not in text
    assert "Nothing changes on the payment side" not in text


def test_fallback_is_counted_as_failure_even_when_risk_matches():
    def failed(*args, **kwargs):
        raise TimeoutError()

    rows, summary = evaluate([DEFAULT_SCRIPTS / "b1_vendor_invoice.txt"], post=failed)
    assert all(row["got"] == "low" for row in rows)
    assert summary["passed"] == 0


def s4_post(url, payload, timeout=None):
    """Kept quote, a paraphrased quote, a `you` quote, and a tactic with no quote."""
    return {"done_reason": "stop", "message": {"content": json.dumps({
        "tactics": ["bypass_approval", "payment_request", "secrecy", "urgency"],
        "evidence": [
            {"tactic": "bypass_approval", "quote": "Skip the second sign-off", "strength": "clear"},
            {"tactic": "payment_request", "quote": "wire the escrow funds", "strength": "clear"},
            {"tactic": "secrecy", "quote": "normally Lisa has to sign off", "strength": "hint"},
        ],
        "claimed_identity": None, "safe_signals": [],
        "reason": "The caller asked to skip an approval.", "next_step": "Call David back.",
    })}}


def verbose_rows(post):
    return evaluate([DEFAULT_SCRIPTS / "s4_partner_wire.txt"], post=post, verbose=True)[0]


def test_verbose_explains_kept_and_dropped_evidence():
    notes = verbose_rows(s4_post)[2]["notes"]
    text = "\n".join(notes)
    assert any(n.startswith("bypass_approval") and "kept" in n for n in notes)
    assert any(n.startswith("payment_request") and "not word-for-word" in n for n in notes)
    assert any(n.startswith("secrecy") and "said by you" in n for n in notes)
    assert any(n.startswith("urgency") and "no evidence quote" in n for n in notes)
    assert "reason:" in text


def test_verbose_names_timeout_fallback():
    def slow(*args, **kwargs):
        raise TimeoutError()

    rows = verbose_rows(slow)
    # beats with a firm cue phrase come back "fast" (watch from the cue alone); never ok
    assert all(r["source"] in ("fallback", "fast") and not r["ok"] for r in rows)
    assert rows[0]["notes"][0].startswith("fallback: model call failed (TimeoutError)")


def test_verbose_flags_cut_off_and_non_json_replies():
    def cut(*args, **kwargs):
        return {"done_reason": "length", "message": {"content": '{"evidence": [{"tac'}}

    notes = verbose_rows(cut)[0]["notes"]
    assert "num_predict" in notes[0]
    assert notes[-1] == "fallback: model reply was not a JSON object"


def test_verbose_quotes_are_capped_and_off_by_default():
    long_quote = "Skip the second sign-off, I'll approve it when I land. " * 3

    def long(*args, **kwargs):
        return {"message": {"content": json.dumps({"evidence": [
            {"tactic": "bypass_approval", "quote": long_quote, "strength": "clear"}],
            "reason": "x", "next_step": "y"})}}

    for note in verbose_rows(long)[1]["notes"]:
        if '"' in note:
            assert len(note.split('"', 1)[1]) <= 82  # 80 chars plus closing quote
    plain, _ = evaluate([DEFAULT_SCRIPTS / "s4_partner_wire.txt"], post=s4_post)
    assert all("notes" not in row for row in plain)
