"""DET-9: beat replay and summary without a live Ollama or transcript output."""
import io
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
