"""UI-14 (cues only): customise the firm rules' cue phrases from the rules panel."""
from ui_replay import Replay

from test_a11y import CONTRAST

# Keep a handle on the iframe's FakeSocket so a test can answer as the Server.
GRAB_SOCKET = """
Object.defineProperty(window, "callguardReplay", {
  configurable: true,
  get() { return this.__hub; },
  set(hub) {
    const attach = hub.attach.bind(hub);
    hub.attach = (sock) => { window.__sock = sock; attach(sock); };
    this.__hub = hub;
  },
});
"""


def is_rules(m):
    return m["type"] == "rules"


def open_editor(page, ui_server, scheme="light"):
    page.add_init_script(GRAB_SOCKET)
    r = Replay(page, ui_server, "s2_vendor_bank")
    r.until(lambda m: m["type"] == "call")  # status + rules delivered, no call yet
    f = r.frame
    f.click("#firm-rules summary")
    f.click("#rules-edit")
    return r, f


def serve(page, msg):
    page.evaluate("(m) => window.__sock.deliver(m)", msg)


def test_add_rule_and_cues_then_save(ui_server, browser):
    page = browser.new_page()
    r, f = open_editor(page, ui_server)
    assert f.is_visible("#rules-editor") and not f.is_visible("#firm-rules-list")
    # a phrase on an existing rule
    f.fill('[data-key="cue-in-no_bank_changes_by_phone"]', "wire it today")
    f.press('[data-key="cue-in-no_bank_changes_by_phone"]', "Enter")
    # too short: inline error, not added
    f.fill('[data-key="cue-in-no_bank_changes_by_phone"]', "ab")
    f.click('[data-key="cue-add-no_bank_changes_by_phone"]')
    assert "3 to 40 characters" in f.inner_text("#rules-errors")
    f.fill('[data-key="cue-in-no_bank_changes_by_phone"]', "")
    # a new cue-only rule: blocked until it has a phrase
    f.fill("#new-rule-text", "We never pay anyone in gift cards.")
    f.press("#new-rule-text", "Enter")
    f.click("#rules-save")
    assert "needs at least one phrase" in f.inner_text("#rules-errors")
    assert r.sent() == []
    cue = f.locator("#rules-edit-list .cue-add input").last
    cue.fill("gift card")
    cue.press("Enter")
    f.click("#rules-save")
    sent = r.sent()
    assert len(sent) == 1 and sent[0]["type"] == "save_rules"
    data = sent[0]["data"]
    bank = next(x for x in data if x["id"] == "no_bank_changes_by_phone")
    assert bank["keywords"][-1] == "wire it today"
    assert data[-1] == {"text": "We never pay anyone in gift cards.", "tactics": [], "keywords": ["gift card"], "enabled": True}
    assert f.is_disabled("#rules-save"), "no double save while waiting"
    # the Server rejects: errors show, editor stays open
    serve(page, {"type": "rules_saved", "data": {"ok": False, "errors": ["Rule 6: example error."]}})
    assert "example error" in f.inner_text("#rules-errors") and f.is_visible("#rules-editor")
    # the Server accepts: new rules arrive, editor closes, note shows
    saved = [*data[:-1], {**data[-1], "id": "custom_we_never_pay_anyone_in_gift_cards"}]
    serve(page, {"type": "rules", "data": saved, "source": "custom"})
    serve(page, {"type": "rules_saved", "data": {"ok": True}})
    assert not f.is_visible("#rules-editor")
    assert "Saved. Applies from the next call." in f.inner_text("#rules-note")
    assert "Your firm's rules (6)" in f.inner_text("#firm-rules summary")
    assert "Listens for: “gift card”" in f.inner_text("#firm-rules-list")
    assert "Set by your firm." in f.inner_text("#firm-rules-src")
    page.close()


def test_remove_cue_switch_off_cancel_and_reset(ui_server, browser):
    page = browser.new_page(color_scheme="dark")
    r, f = open_editor(page, ui_server)
    f.fill('[data-key="cue-in-no_bank_changes_by_phone"]', "new account")
    f.click('[data-key="cue-add-no_bank_changes_by_phone"]')
    f.click('[aria-label="Remove phrase new account"]')
    assert "new account" not in f.inner_text("#rules-edit-list")
    f.uncheck('[data-key="on-never_keep_calls_secret"]')
    assert not f.evaluate(CONTRAST), "text below 4.5:1"
    f.click("#rules-cancel")
    assert r.sent() == [] and not f.is_visible("#rules-editor")
    assert "Off" not in f.inner_text("#firm-rules-list"), "cancel drops the draft"
    f.click("#rules-edit")
    f.click("#rules-reset")
    assert r.sent() == [], "reset needs a second click"
    f.click("#rules-reset")
    assert r.sent() == [{"type": "reset_rules"}]
    serve(page, {"type": "rules_saved", "data": {"ok": True}})
    assert "Back to the default rules." in f.inner_text("#rules-note")
    page.close()


def test_editor_locked_during_a_call(ui_server, browser):
    page = browser.new_page()
    r, f = open_editor(page, ui_server)
    r.one()  # call started
    assert f.is_disabled("#rules-save") and f.is_disabled("#rules-reset")
    assert "after the call" in f.inner_text("#rules-errors")
    f.click("#rules-cancel")
    assert f.is_disabled("#rules-edit") and f.is_visible("#rules-lock")
    page.close()
