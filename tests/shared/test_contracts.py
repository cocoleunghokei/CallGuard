"""QA-SH-01..04: contracts.py and AGENTS.md section 3 stay in sync (hack1984/qa-test-plan.md §2)."""
import json
import re
from pathlib import Path
from typing import get_type_hints

from callguard.shared import contracts as c

ROOT = Path(__file__).resolve().parents[2]
AGENTS = (ROOT / "AGENTS.md").read_text()
PRD = (ROOT / "hack1984" / "prd.md").read_text()


def _section3() -> str:
    start = AGENTS.index("## 3. Contracts")
    return AGENTS[start:AGENTS.index("## 4.", start)]


def _json_example(after_heading: str) -> dict:
    """First ```json block after a bold heading like **`ScamCheck`** in AGENTS.md §3."""
    sec = _section3()
    i = sec.index(after_heading)
    block = re.search(r"```json\n(.*?)```", sec[i:], re.S).group(1)
    # The doc writes enum choices as "a | b"; any string is fine for a key check.
    return json.loads(block)


def test_qa_sh_01_tactics_match_weights_table_and_agents_md():
    weights = set(re.findall(r"^\| `(\w+)`(?: \*\(v2\)\*)? \| 0\.\d+ \|", PRD, re.M))
    assert weights == set(c.TACTICS), f"prd §6.3 weights vs TACTICS: {weights ^ set(c.TACTICS)}"
    doc_tactics = set(_json_example("**`ScamCheck`**")["tactics"])
    assert doc_tactics == set(c.TACTICS), f"AGENTS.md §3 vs TACTICS: {doc_tactics ^ set(c.TACTICS)}"


def _check_keys(example: dict, td) -> None:
    keys = set(get_type_hints(td).keys())
    required = set(td.__required_keys__)
    assert required <= set(example), f"{td.__name__}: missing {required - set(example)}"
    assert set(example) <= keys, f"{td.__name__}: unknown {set(example) - keys}"


def test_qa_sh_02_agents_md_examples_match_typeddicts():
    _check_keys(_json_example("**`TranscriptChunk`**"), c.TranscriptChunk)
    _check_keys(_json_example("**`Rule`**"), c.Rule)
    sc = _json_example("**`ScamCheck`**")
    _check_keys(sc, c.ScamCheck)
    for ev in sc["evidence"]:
        _check_keys(ev, c.Evidence)
    _check_keys(_json_example("**`EgressEntry`**"), c.EgressEntry)


def test_qa_sh_03_message_types_documented_both_ways():
    sec = _section3()
    server_part = sec[sec.index("Every message from the Server"):sec.index("UI → Server")]
    client_part = sec[sec.index("UI → Server"):]
    doc_server = set(re.findall(r"^\| `(\w+)` \|", server_part, re.M)) - {"type"}  # header row
    doc_client = set(re.findall(r"^\| `(\w+)` \|", client_part, re.M)) - {"type"}
    assert doc_server == set(c.MessageType.__args__), doc_server ^ set(c.MessageType.__args__)
    assert doc_client == set(c.ClientMessageType.__args__), doc_client ^ set(c.ClientMessageType.__args__)


V1_REQUIRED = {
    "TranscriptChunk": {"speaker", "text", "start", "end", "language"},
    "Rule": {"id", "text", "tactics"},
    "ScamCheck": {"risk", "tactics", "claimed_identity", "rules_broken", "reason", "next_step"},
    "EgressEntry": {"time", "destination", "sent", "status"},
}


def test_qa_sh_04_v2_fields_are_optional():
    for name, req in V1_REQUIRED.items():
        td = getattr(c, name)
        assert set(td.__required_keys__) == req, f"{name}: required keys changed (guardrail 7)"
