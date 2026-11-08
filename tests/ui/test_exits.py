"""T7 / UI-5: the pause (gate) and the three safe exits.

Static checks always run. The browser checks replay S1 through the harness,
keyboard only, and skip cleanly without Python Playwright or Chromium.
"""
import pathlib
import re

import pytest
from ui_replay import Replay, is_danger, is_end, is_gate_locked

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


def test_exit_buttons_in_tab_order():
    html = (UI / "index.html").read_text(encoding="utf-8")
    exits = html[html.index('id="ov-exits"') :]
    assert 'id="ov-hangup"' not in exits, "the hang-up exit was removed (Coco, Sat)"
    order = [exits.index(x) for x in ['id="ov-colleague"', 'id="safe-input"', 'id="safe-hold"']]
    assert order == sorted(order), "Tab order must be Report scam -> SAFE input -> hold"
    assert re.search(r'<button id="safe-hold"[^>]*\bdisabled\b', html), "hold starts disabled"
    assert "tabindex=\"1" not in html and "tabindex=\"2" not in html, "no positive tabindex"


def test_pause_copy_never_claims_typing_is_blocked():
    """AGENTS.md 3: the safe-path pause never blocks typing."""
    for f in [UI / "index.html", UI / "copy.js", UI / "view.js", UI / "DEMO.md", UI / "SCREENS.md"]:
        assert "Typing is paused" not in f.read_text(encoding="utf-8"), f.name


def test_hold_is_three_seconds():
    assert "const HOLD_MS = 3000;" in (UI / "view.js").read_text(encoding="utf-8")


# ---------------------------------------------------------------- browser


def locked_s1(page, ui_server):
    r = Replay(page, ui_server, "s1_government")
    assert r.until(is_gate_locked)
    r.one()
    assert r.frame.is_visible("#overlay")
    # Clicking the harness's Step button moved keyboard focus to the parent page;
    # hand it back to where the overlay put it (checked in test_overlay.py).
    r.frame.focus("#ov-colleague")
    return r


def test_no_pause_warning_stays_until_an_exit(ui_server, browser):
    """The pause was removed (Coco, Sat): `gate` is ignored, no countdown, no step-back."""
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    assert f.locator("#ov-lock, #ov-count").count() == 0
    r.one()  # the Server's gate off (sent only when CALLGUARD_GATE=on): nothing changes
    assert f.is_visible("#overlay")
    assert r.sent() == []
    page.close()


def test_enter_and_esc_never_take_an_exit(ui_server, browser):
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    assert f.evaluate("document.activeElement.id") == "ov-colleague"
    for _ in range(3):  # visit every exit by keyboard, pressing Enter and Esc on each
        page.keyboard.press("Enter")
        page.keyboard.press("Escape")
        page.keyboard.press("Tab")
    assert f.is_visible("#overlay")
    assert r.sent() == []
    page.close()


def test_check_with_a_colleague(ui_server, browser):
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    assert f.evaluate("document.activeElement.id") == "ov-colleague"
    page.keyboard.press(" ")
    assert r.sent() == [{"type": "colleague"}, {"type": "gate_release", "how": "colleague"}]
    toast = f.inner_text("#ov-toast")
    assert "Heads-up for IT and your manager" in toast and "IT team and your manager" in toast and "Demo" not in toast
    assert "Department of Justice" not in toast, "fixed wording only, nothing from the call"
    assert f.inner_text("#priv-text").startswith("1 search sent"), "the heads-up adds nothing to the egress log"
    assert f.is_visible("#overlay")
    page.close()


def test_safe_needs_the_word(ui_server, browser):
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    f.fill("#safe-input", "SAF")
    assert f.is_disabled("#safe-hold")
    r.hold_safe(3300, text="SAF")
    assert r.sent() == []
    f.fill("#safe-input", "safe")  # case-insensitive
    assert not f.is_disabled("#safe-hold")
    page.close()


def test_safe_hold_shorter_than_3s_does_nothing(ui_server, browser):
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    r.hold_safe(2900)
    assert r.sent() == []
    assert f.is_visible("#overlay")
    f.click("#safe-hold")  # a single click never marks safe
    page.keyboard.press(" ")  # nor a single keypress
    assert r.sent() == []
    page.close()


def test_safe_hold_3s_marks_safe(ui_server, browser):
    page = browser.new_page()
    r = locked_s1(page, ui_server)
    f = r.frame
    # keyboard only: Tab Report scam -> input -> hold
    page.keyboard.press("Tab")
    assert f.evaluate("document.activeElement.id") == "safe-input"
    page.keyboard.type("Safe")
    page.keyboard.press("Tab")
    assert f.evaluate("document.activeElement.id") == "safe-hold"
    page.keyboard.down(" ")
    page.wait_for_timeout(3300)
    page.keyboard.up(" ")
    assert r.sent() == [{"type": "mark_safe"}, {"type": "gate_release", "how": "mark_safe"}]
    assert not f.is_visible("#overlay")
    assert f.inner_text("#hero-word") == "Low"
    assert f.inner_text("#hero-words") == "Marked safe"
    page.close()


@pytest.mark.parametrize("button", ["#ov-colleague"])
def test_exits_work_without_a_gate(button, ui_server, browser):
    """Pure danger, no ask: every button still works."""
    page = browser.new_page()
    r = Replay(page, ui_server, "s1_government")
    r.until(is_danger)
    r.one()
    r.frame.click(button)
    assert r.sent()[-1]["type"] == "gate_release"
    page.close()
