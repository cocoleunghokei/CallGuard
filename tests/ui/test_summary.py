"""T11 / UI-10: after-call summary cards in the History tab. No transcript, no quotes, gone when removed."""
import json
import pathlib
import re

import pytest
from ui_replay import Replay, is_end, is_gate_locked

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"
FIXTURES = UI / "dev" / "fixtures"

STATE = "async () => (await import('/app.js')).state.history"
CARD = "#history-list > li:first-child"


def play_to_end(r):
    r.until(is_end)
    r.one()


def call_words(name):
    """Everything the caller (or user) said in this fixture, plus the claimed identity and phone."""
    steps = [s["msg"] for s in json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["steps"]]
    out = [m["data"]["text"] for m in steps if m["type"] == "transcript"]
    for m in steps:
        d = m["data"]
        if m["type"] == "check":
            out += [e["quote"] for e in d.get("evidence", [])]
            if d.get("claimed_identity"):
                out.append(d["claimed_identity"])
        if m["type"] == "verify" and d.get("phone"):
            out.append(d["phone"])
    return out


def test_card_copy_has_no_banned_words():
    copy = (UI / "copy.js").read_text(encoding="utf-8")
    block = copy[copy.index("const CALL_KINDS") :]
    assert not re.search(r"\b(fraud\w*|scam\w*|attack\w*)\b", block, re.I)


@pytest.mark.parametrize(
    "name,kind,outcome",
    [
        ("s1_government", "Someone posing as an official", "you reported it"),
        ("s2_vendor_bank", "Someone asking to change bank details", "you reported it"),
        ("s3_it_code", "Someone asking for a login code", "you reported it"),
        ("s4_partner_wire", "Someone pushing for a payment", "you reported it"),
    ],
)
def test_card_after_report(name, kind, outcome, ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, name)
    f = r.frame
    r.until(is_gate_locked)
    r.one()
    f.click("#ov-colleague")
    play_to_end(r)
    assert not f.is_visible("#history"), "the card waits in its own tab"
    assert f.is_visible("#tab-history-dot")
    f.click("#tab-history")
    assert not f.is_visible("#tab-history-dot")
    assert f.inner_text(f"{CARD} .sum-kind") == kind
    line = f.inner_text(f"{CARD} .sum-line")
    assert line.startswith("Reached Danger · ") and outcome in line and re.search(r"\d+ warning signs?", line)
    card = f.inner_text("#history")
    for words in call_words(name):
        assert words not in card, f"call content in the summary: {words[-80:]!r}"
    page.close()


def test_no_exit_taken(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s1_government")
    play_to_end(r)  # no exit taken: the card names no outcome (the pause, and "ran out", are gone)
    r.frame.click("#tab-history")
    line = r.frame.inner_text(f"{CARD} .sum-line")
    assert line.startswith("Reached Danger · ") and "pause" not in line
    page.close()

def test_watch_only_call_and_mark_safe(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "model_down")  # tops out at Watch
    f = r.frame
    r.until(lambda m: m["type"] == "check" and m["data"].get("risk") == "watch")
    r.one()
    f.click("#side-safe")
    play_to_end(r)
    f.click("#tab-history")
    assert f.inner_text(f"{CARD} .sum-line").startswith("Reached Watch · ")
    assert "you marked it safe" in f.inner_text(f"{CARD} .sum-line")
    page.close()


@pytest.mark.parametrize("name", ["b1_vendor_invoice", "b2_colleague", "b3_real_bank", "b7_you_say_it"])
def test_calm_calls_leave_no_card(name, ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, name)
    play_to_end(r)
    assert not r.frame.is_visible("#tab-history-dot")
    assert r.frame.evaluate(STATE) == []
    page.close()


def test_dismiss_clears_memory_and_dom(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s2_vendor_bank")
    f = r.frame
    play_to_end(r)
    assert f.evaluate(STATE)[0]["tactics"]
    f.click("#tab-history")
    f.click(f"{CARD} [data-act=copy]")  # user's own action; must not throw without clipboard permission
    f.click(f"{CARD} [data-act=remove]")
    assert f.evaluate(STATE) == []
    assert f.locator("#history-list > li").count() == 0
    assert f.is_visible("#history-empty")
    page.close()
