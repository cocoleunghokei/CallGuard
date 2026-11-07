"""DET-8: structural checks for the scenario scripts (prd §15.2, eval-suite §3.2).

Other lanes replay these files (audio.fake_stream), so a malformed header here
breaks their demos too. No model, no network.
"""
from pathlib import Path

import pytest

from callguard.shared.contracts import TACTICS

SCRIPTS = Path(__file__).parent / "scripts"
P0_IDS = {
    "s1_government", "s2_vendor_bank", "s3_it_code", "s4_partner_wire",
    "b1_vendor_invoice", "b2_colleague_deadline", "b3_real_bank", "b7_you_say_it",
}
RISKS = {"low", "watch", "danger"}


def parse(path: Path):
    headers, lines = {}, []
    for raw in path.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        if raw.startswith("#"):
            key, _, value = raw[1:].partition(":")
            headers[key.strip()] = value.split("  #")[0].strip()
            continue
        speaker, sep, text = raw.partition(":")
        assert sep, f"{path.name}: line without speaker: {raw[-80:]}"
        lines.append((speaker.strip(), text.strip()))
    return headers, lines


def listed(value: str) -> list[str]:
    return [] if value in ("", "-") else [v.strip() for v in value.split(",")]


ALL = sorted(SCRIPTS.glob("*.txt"))


def test_p0_set_present():
    assert P0_IDS <= {p.stem for p in ALL}


@pytest.mark.parametrize("path", ALL, ids=lambda p: p.stem)
def test_script_is_well_formed(path):
    h, lines = parse(path)
    assert h["id"] == path.stem
    assert h.get("set") in {"p0", "p1", "variant"}
    assert h.get("kind") in {"scam", "twin"}

    speakers = {s for s, _ in lines}
    assert speakers <= {"caller", "you"}
    assert "you" in speakers, "every script has at least one you: line (eval-suite §3.3)"
    assert all(t for _, t in lines)

    caller_beats = sum(1 for s, _ in lines if s == "caller")
    expect = [set(e.strip().split("|")) for e in h["expect"].split(",")]
    assert len(expect) == caller_beats, "one expect entry per caller line"
    assert all(e <= RISKS for e in expect)

    for key in ("giveaway", "gate"):
        if key in h:
            assert 1 <= int(h[key]) <= caller_beats

    assert set(listed(h.get("tactics", ""))) <= set(TACTICS)

    if h["kind"] == "scam":
        assert "danger" in expect[-1]
        g = int(h["giveaway"])
        assert all("danger" in e for e in expect[g - 1:]), "danger from the giveaway on (sticky)"
        assert all(e != {"danger"} for e in expect[: g - 1]), "no danger before the giveaway"
    else:
        assert all("danger" not in e for e in expect), "twins never reach danger"
        assert "gate" not in h
