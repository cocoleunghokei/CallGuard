"""T6 / UI-4: the danger overlay.

Static checks always run. The browser checks replay fixtures through the
harness and skip cleanly without Python Playwright or Chromium.
"""
import pathlib
import re

import pytest
from ui_replay import Replay, is_danger, is_end

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


def test_overlay_markup():
    html = (UI / "index.html").read_text(encoding="utf-8")
    tag = re.search(r'<div id="overlay"[^>]*>', html).group(0)
    assert 'role="alertdialog"' in tag and 'aria-labelledby="ov-h"' in tag and 'aria-modal="true"' in tag
    assert re.search(r'<h1 id="ov-h">Scam detected</h1>', html)
    assert 'data-exit="hang_up"' not in html and 'data-exit="colleague"' in html


def test_tone_is_generated_not_loaded():
    view = (UI / "view.js").read_text(encoding="utf-8")
    assert "createOscillator" in view
    assert not re.search(r"new Audio\(|\.(mp3|wav|m4a|ogg)\b", view)
    assert not list(UI.rglob("*.mp3")) + list(UI.rglob("*.wav"))


def test_wide_window_gets_a_centred_card():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"@media \(min-width: 701px\)\s*\{[^@]*\.ov-card \{ max-width: 720px;", css)


# ---------------------------------------------------------------- browser

DANGER = {
    "s1_government": ["Department of Justice", "Do not tell your colleagues or your firm", "Firm rule:", "(202) 514-2000"],
    "s2_vendor_bank": [
        "Brightline Supplies",
        "Firm rule: We never change vendor or client bank details because of a phone call",
        "use the one on file",
    ],
    "s3_it_code": ["Asks for a code or password", "Firm rule: IT will never ask you for a code or password."],
    "s4_partner_wire": ["Asks you to send money", "Firm rule: Every wire needs two approvals"],
}


@pytest.mark.parametrize("name", sorted(DANGER))
def test_danger_opens_overlay_that_explains_itself(name, ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, name)
    assert r.until(is_danger)
    r.one()
    f = r.frame
    assert f.is_visible("#overlay")
    assert f.evaluate("document.activeElement.id") == "ov-colleague"
    assert f.evaluate("document.getElementById('main').inert")

    # Esc and Enter never close it.
    f.press("#ov-colleague", "Escape")
    f.press("#ov-colleague", "Enter")
    assert f.is_visible("#overlay")

    assert r.until(is_end)
    text = f.inner_text("#overlay")
    assert f.locator("#ov-tactics q").count() >= 1, "tactic rows carry the caller's words"
    for want in DANGER[name]:
        assert want in text, want
    assert f.inner_text("#ov-next").strip()
    assert f.evaluate("window.__tones") == 1, "one tone per open, not per danger check"

    r.one()  # call ended
    assert not f.is_visible("#overlay")
    assert not f.evaluate("document.getElementById('main').inert")
    page.close()


@pytest.mark.parametrize("name", ["model_down", "b1_vendor_invoice", "b2_colleague", "b3_real_bank", "b7_you_say_it"])
def test_no_overlay_without_danger(name, ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, name)
    while not page.locator("#step").is_disabled():
        page.click("#step")
        assert not r.frame.is_visible("#overlay")
    page.close()


def test_closed_overlay_reopens_only_for_a_new_tactic(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s1_government")
    f = r.frame
    r.until(is_danger)
    r.one()
    r.mark_safe()
    assert not f.is_visible("#overlay") and f.inner_text("#hero-word") == "Low"
    r.until(is_danger)  # the next danger check adds a new ask tactic
    r.one()
    assert f.is_visible("#overlay")
    assert f.evaluate("window.__tones") == 2
    page.close()


def test_same_tactics_do_not_reopen(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s2_vendor_bank")
    f = r.frame
    r.until(is_danger)
    r.one()
    r.mark_safe()
    r.until(is_danger)
    r.one()
    assert not f.is_visible("#overlay") and f.inner_text("#hero-word") == "Danger"
    f.click("#show-warning")
    assert f.is_visible("#overlay")
    assert f.evaluate("window.__tones") == 1, "reopening by hand is not a new alert"
    page.close()


def test_verify_line_hides_when_no_lookup_arrives(ui_server, browser):
    """S3/S4 claim internal identities the Server never searches: "Checking…" must not stay forever."""
    page = browser.new_page()
    r = Replay(page, ui_server, "s3_it_code")
    f = r.frame
    r.until(is_danger)
    r.one()
    assert "Checking" in f.inner_text("#ov-verify")
    page.wait_for_timeout(5300)
    assert not f.is_visible("#ov-verify")
    page.close()


@pytest.mark.parametrize(
    "name,expected",
    [
        ("s1_report", "Reported: Callers posing as DOJ staff asking for bank details · consumer.ftc.gov, Oct 2026"),
        ("s1_government", None),  # no report on verify: no line
        ("offline", None),  # offline: no line
    ],
)
def test_report_line(name, expected, ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, name)
    r.until(is_danger)
    r.one()
    f = r.frame
    if expected:
        assert f.inner_text("#ov-report") == expected
    else:
        assert not f.is_visible("#ov-report")
    page.close()
