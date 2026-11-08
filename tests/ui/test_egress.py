"""T5 / UI-6: "What left this device".

Static checks always run. The browser checks replay fixtures through the
harness and skip cleanly without Python Playwright or Chromium.
"""
import json
import pathlib
import re

import pytest

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"
FIXTURES = UI / "dev" / "fixtures"


def test_markup_has_header_count_and_empty_state():
    html = (UI / "index.html").read_text(encoding="utf-8")
    assert re.search(r'Sent online \(<span id="egress-n">0</span>\)', html)
    assert "Nothing sent online" in html
    assert "Your call stays on this laptop" in html
    assert 'id="priv-btn"' in html and 'aria-controls="egress"' in html


def test_every_egress_status_has_a_word():
    view = (UI / "view.js").read_text(encoding="utf-8")
    block = view[view.index("const EGRESS_STATUS") :]
    block = block[: block.index("};")]
    for status in ["ok", "error", "offline", "refused"]:
        assert re.search(rf"\b{status}: \{{ word: \"[^\"]+\"", block), status


def test_refused_copy_matches_lane_spec():
    assert "Blocked: lookup skipped to protect your privacy" in (UI / "view.js").read_text(encoding="utf-8")


def test_flash_respects_reduced_motion():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"prefers-reduced-motion: reduce\)\s*\{\s*\.priv-row\.flash \{ animation: none; \}", css)
    assert "prefers-reduced-motion" in (UI / "view.js").read_text(encoding="utf-8")


def test_egress_handler_keeps_only_entry_fields():
    """Entries are stored as sent by the Server plus seq/call tags: no transcript can ride along."""
    app = (UI / "app.js").read_text(encoding="utf-8")
    assert "state.egress.unshift({ ...data, seq: state.egress.length + 1, call: state.inCall ? state.calls : 0 });" in app


# ---------------------------------------------------------------- browser

def _play(page, ui_server, name):
    page.goto(f"{ui_server}/dev/replay.html?f={name}&autoplay=0")
    page.wait_for_function("!document.getElementById('clock').textContent.includes('waiting')")
    frame = page.frame(url=re.compile(r"index\.html"))
    frame.click("#priv-btn")
    during = None
    steps = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["steps"]
    for i, step in enumerate(steps):
        if page.locator("#step").is_disabled():
            break
        page.click("#step")
        if step["msg"]["type"] == "call" and step["msg"]["data"]["state"] == "ended":
            break
        during = frame.inner_text("#egress")
    return frame, during


def test_b1_stays_empty(ui_server, browser):
    page = browser.new_page()
    frame, during = _play(page, ui_server, "b1_vendor_invoice")
    assert "Sent online (0)" in during
    assert frame.is_visible("#egress-empty")
    assert frame.inner_text("#priv-text") == "Nothing sent online"
    page.close()


@pytest.mark.parametrize("name,status", [("s1_government", "Sent"), ("offline", "Offline, not sent")])
def test_s1_shows_one_org_entry(name, status, ui_server, browser):
    page = browser.new_page()
    frame, during = _play(page, ui_server, name)
    assert "Sent online (1)" in during
    assert frame.locator(".eg-row").count() == 1
    row = frame.inner_text(".eg-row")
    assert "Department of Justice" in row and "api.tavily.com" in row and status in row
    expected = "1 search sent" if name == "s1_government" else "Nothing sent online"
    assert frame.inner_text("#priv-text").startswith(expected)
    page.close()
