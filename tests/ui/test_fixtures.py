"""UI-8: replay fixtures are valid and match the contracts. No browser needed."""
import json
import pathlib
import re
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from callguard.shared import contracts  # noqa: E402

FIXTURES_DIR = ROOT / "ui" / "dev" / "fixtures"
FIXTURE_FILES = sorted(FIXTURES_DIR.glob("*.json"))
CALL_FIXTURES = [p for p in FIXTURE_FILES if p.stem != "idle"]

KNOWN_TYPES = set(contracts.MessageType.__args__) | {"gate", "call", "rules"}
KNOWN_TACTICS = set(contracts.TACTICS)
P0_RULES = {
    "no_bank_changes_by_phone",
    "it_never_asks_for_codes",
    "wires_need_two_approvals",
    "government_never_calls_for_payment_or_bank_details",
    "never_keep_calls_secret",
}
REQUIRED = {
    "idle", "s1_government", "s2_vendor_bank", "s3_it_code", "s4_partner_wire",
    "b1_vendor_invoice", "b2_colleague", "b3_real_bank", "b7_you_say_it",
    "offline", "model_down",
}
# UI copy rules (prd.md 9.3). Caller speech in transcripts/quotes is exempt.
BANNED_COPY = re.compile(r"\b(fraud\w*|scam\w*|attack\w*)\b", re.I)


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def msgs(path, type_=None):
    return [s["msg"] for s in load(path)["steps"] if type_ is None or s["msg"]["type"] == type_]


def test_all_required_fixtures_exist():
    assert REQUIRED <= {p.stem for p in FIXTURE_FILES}


def test_replay_picker_lists_every_fixture():
    js = (ROOT / "ui" / "dev" / "replay.js").read_text(encoding="utf-8")
    block = re.search(r"FIXTURES = \[(.*?)\]", js, re.S).group(1)
    assert set(re.findall(r'"([\w]+)"', block)) == {p.stem for p in FIXTURE_FILES}


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_shape_and_order(path):
    doc = load(path)  # valid JSON
    assert doc["id"] == path.stem
    assert doc["description"]
    ats = [s["at"] for s in doc["steps"]]
    assert ats, "no steps"
    assert all(isinstance(a, (int, float)) and a >= 0 for a in ats)
    assert ats == sorted(ats), "steps must be sorted by 'at'"
    for s in doc["steps"]:
        assert s["msg"]["type"] in KNOWN_TYPES, s["msg"]["type"]
        assert "data" in s["msg"]


@pytest.mark.parametrize("path", FIXTURE_FILES, ids=lambda p: p.stem)
def test_transcript_lines_are_short(path):
    for m in msgs(path, "transcript"):
        d = m["data"]
        assert len(d["text"]) <= 200
        assert d["speaker"] in ("caller", "you")
        assert d["end"] >= d["start"]


@pytest.mark.parametrize("path", CALL_FIXTURES, ids=lambda p: p.stem)
def test_call_lifecycle(path):
    seq = msgs(path)
    types = [m["type"] for m in seq]
    assert types[0] == "status"
    assert seq[-1] == {"type": "call", "data": {"state": "ended"}}
    started = types.index("call")
    assert seq[started]["data"]["state"] == "started"
    rules_at = types.index("rules")
    assert rules_at < started, "rules come near the start, before the call"
    ids = {r["id"] for r in seq[rules_at]["data"]}
    assert P0_RULES <= ids


@pytest.mark.parametrize("path", CALL_FIXTURES, ids=lambda p: p.stem)
def test_checks_match_contract(path):
    rule_ids = {r["id"] for r in msgs(path, "rules")[0]["data"]}
    caller_text = " ".join(m["data"]["text"] for m in msgs(path, "transcript") if m["data"]["speaker"] == "caller")
    for m in msgs(path, "check"):
        d = m["data"]
        assert d["risk"] in ("low", "watch", "danger")
        assert set(d["tactics"]) <= KNOWN_TACTICS
        assert set(d["rules_broken"]) <= rule_ids
        assert 0 <= d.get("confidence", 0) <= 1
        assert not BANNED_COPY.search(d["reason"] + " " + d["next_step"]), d["reason"]
        for e in d.get("evidence", []):
            assert e["tactic"] in KNOWN_TACTICS
            assert len(e["quote"]) <= 80
            assert e["speaker"] == "caller"
            assert e["quote"] in caller_text, f"quote not verbatim: {e['quote']!r}"


def test_idle_has_no_call():
    assert not msgs(FIXTURES_DIR / "idle.json", "call")
    assert not msgs(FIXTURES_DIR / "idle.json", "egress")


@pytest.mark.parametrize("name", ["s1_government", "s2_vendor_bank", "s3_it_code", "s4_partner_wire"])
def test_scams_reach_danger_and_lock(name):
    path = FIXTURES_DIR / f"{name}.json"
    assert any(m["data"]["risk"] == "danger" for m in msgs(path, "check"))
    assert any(m["data"]["state"] == "locked" for m in msgs(path, "gate"))


@pytest.mark.parametrize("name", ["b1_vendor_invoice", "b2_colleague", "b3_real_bank", "b7_you_say_it"])
def test_benign_twins_stay_low(name):
    path = FIXTURES_DIR / f"{name}.json"
    assert all(m["data"]["risk"] == "low" for m in msgs(path, "check"))
    assert not msgs(path, "gate")
    assert not msgs(path, "egress")


def test_s1_sends_only_the_org_name():
    eg = msgs(FIXTURES_DIR / "s1_government.json", "egress")
    assert [e["data"]["sent"] for e in eg] == ["Department of Justice"]
    assert eg[0]["data"]["status"] == "ok"


def test_offline_is_s1_with_three_differences():
    off = FIXTURES_DIR / "offline.json"
    assert msgs(off, "status")[0]["data"]["online"] is False
    assert [v["data"].get("status") for v in msgs(off, "verify")] == ["offline"]
    assert [e["data"]["status"] for e in msgs(off, "egress")] == ["offline"]
    s1 = FIXTURES_DIR / "s1_government.json"
    assert [m["data"]["risk"] for m in msgs(off, "check")] == [m["data"]["risk"] for m in msgs(s1, "check")]


def test_model_down_caps_at_watch():
    path = FIXTURES_DIR / "model_down.json"
    assert msgs(path, "status")[0]["data"]["model"] == "degraded"
    checks = [m["data"] for m in msgs(path, "check")]
    assert all(c["risk"] in ("low", "watch") for c in checks)
    assert any(c.get("source") == "fallback" for c in checks)
    assert not msgs(path, "gate")
