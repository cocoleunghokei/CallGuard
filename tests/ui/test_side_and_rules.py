"""T10: side buttons at Watch (UI-9) and the read-only firm rules panel (UI-13)."""
import pytest
from ui_replay import Replay, is_end

from test_a11y import CONTRAST


def is_watch(m):
    return m["type"] == "check" and m["data"].get("risk") == "watch"


def is_check(m):
    return m["type"] == "check"


def test_s1_buttons_at_watch_only(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s1_government")
    f = r.frame
    r.until(is_watch)
    assert not f.is_visible("#actions"), "not at low"
    r.one()
    assert f.is_visible("#side-colleague") and f.is_visible("#side-safe")
    f.click("#side-colleague")
    assert r.sent() == [{"type": "colleague"}], "no gate_release outside danger"
    toast = f.inner_text("#panel-toast")
    assert "Heads-up for IT and your manager" in toast and "Demo: not sent" in toast
    f.click("#side-safe")  # one click is enough outside danger
    assert r.sent()[-1] == {"type": "mark_safe"}
    assert f.inner_text("#hero-word") == "Low" and f.inner_text("#hero-words") == "Marked safe"
    assert not f.is_visible("#actions")
    page.close()


@pytest.mark.parametrize("scheme", ["light", "dark"])
def test_s2_bank_rule_badge_and_reset(scheme, ui_server, browser):
    page = browser.new_page(color_scheme=scheme)
    r = Replay(page, ui_server, "s2_vendor_bank")
    f = r.frame
    r.until(is_check)  # rules arrived, call started
    assert not f.is_visible("#firm-rules"), "rules live in their own tab"
    f.click("#tab-rules")
    assert "Your firm's rules (5)" in f.inner_text("#firm-rules-h")
    f.click("#tab-call")
    # danger opens the overlay; mark safe by hand to look at the panel underneath
    while r.next_index() < len(r.steps) and not (is_check(r.steps[r.next_index()]) and r.steps[r.next_index()]["data"]["risk"] == "danger"):
        r.one()
    r.one()
    r.mark_safe()
    f.click("#tab-rules")
    rows = f.locator("#firm-rules-list li")
    bank = [rows.nth(i).inner_text() for i in range(rows.count()) if "bank details because of a phone call" in rows.nth(i).inner_text()]
    assert bank and "came up 1×" in bank[0]
    assert "1 came up this call" in f.inner_text("#firm-rules .view-h")
    assert not f.evaluate(CONTRAST), "text below 4.5:1"
    r.until(is_end)
    r.one()
    assert "came up" not in f.inner_text("#firm-rules"), "badges reset with the call"
    page.close()
