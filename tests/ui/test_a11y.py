"""T8: accessibility audit on the demo path (S1). Browser checks skip without Playwright."""
import pathlib
import re

import pytest
from ui_replay import Replay, is_danger, is_gate_locked

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"

FOCUS_RING = """() => { const el = document.activeElement; if (!el || el === document.body) return null;
  const cs = getComputedStyle(el);
  return {id: el.id || el.className || el.tagName, style: cs.outlineStyle, width: parseFloat(cs.outlineWidth)}; }"""

# WCAG contrast of every visible text node against its effective background.
CONTRAST = r"""() => {
  const parse = (c) => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const [r,g,b,a=1] = m[1].split(/[ ,\/]+/).filter(Boolean).map(Number); return {r,g,b,a}; };
  const lum = ({r,g,b}) => { const f = v => { v/=255; return v <= .03928 ? v/12.92 : ((v+.055)/1.055)**2.4; }; return .2126*f(r)+.7152*f(g)+.0722*f(b); };
  const blend = (fg, bg) => ({ r: fg.r*fg.a + bg.r*(1-fg.a), g: fg.g*fg.a + bg.g*(1-fg.a), b: fg.b*fg.a + bg.b*(1-fg.a), a: 1 });
  const bgOf = (el) => { const st = []; for (let e = el; e; e = e.parentElement) { const c = parse(getComputedStyle(e).backgroundColor); if (c && c.a > 0) { st.push(c); if (c.a >= 1) break; } }
    let bg = {r:255,g:255,b:255,a:1}; if (st.length && st[st.length-1].a >= 1) bg = st.pop(); for (const c of st.reverse()) bg = blend(c, bg); return bg; };
  const out = []; const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let n; (n = w.nextNode()); ) {
    if (!n.textContent.trim()) continue; const el = n.parentElement; const cs = getComputedStyle(el);
    if (!el.offsetParent && cs.position !== 'fixed') continue; const r = el.getBoundingClientRect(); if (!r.width || !r.height) continue;
    let fg = parse(cs.color); let op = 1; for (let e = el; e; e = e.parentElement) op *= Number(getComputedStyle(e).opacity);
    const bg = bgOf(el); const f2 = blend({ ...fg, a: fg.a * op }, bg); const A = lum(f2), B = lum(bg);
    const ratio = (Math.max(A,B)+.05)/(Math.min(A,B)+.05); if (ratio < 4.5) out.push(`${ratio.toFixed(2)} ${n.textContent.trim().slice(0,40)}`);
  } return out; }"""


def test_reduced_motion_covers_transitions_and_flash():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    assert re.search(r"prefers-reduced-motion: reduce\)\s*\{\s*:root \{ --dur: 0ms; \}", css)
    assert "transition" in css and not re.search(r"transition:[^;]*\d+m?s", css), "transitions use var(--dur)"


def test_focus_ring_rule():
    css = (UI / "styles.css").read_text(encoding="utf-8")
    assert ":focus-visible { outline: 2px solid var(--focus);" in css
    assert not re.search(r"outline:\s*(none|0)\b(?![^}]*:focus\b)", css.replace(".overlay:focus { outline: none; }", ""))


def _tab_all(page, frame, limit=30):
    seen, bad = [], []
    for _ in range(limit):
        page.keyboard.press("Tab")
        ring = frame.evaluate(FOCUS_RING)
        if not ring:
            continue
        if ring["id"] in seen:
            break
        seen.append(ring["id"])
        if ring["style"] == "none" or ring["width"] < 2:
            bad.append(ring)
    return seen, bad


@pytest.mark.parametrize("scheme", ["light", "dark"])
@pytest.mark.parametrize("beat", ["watch", "locked", "panel_danger"])
def test_demo_path_contrast_and_focus(beat, scheme, ui_server, browser):
    page = browser.new_page(color_scheme=scheme)
    r = Replay(page, ui_server, "s1_government")
    f = r.frame
    if beat == "watch":
        r.until(lambda m: m["type"] == "check" and m["data"].get("risk") == "watch")
        r.one()
        start = "#consent-x"
    else:
        r.until(is_gate_locked)
        r.one()
        start = "#ov-colleague"
        if beat == "panel_danger":
            r.one()  # auto-release: back to the red panel
            start = "#show-warning"
    assert not f.evaluate(CONTRAST), "text below 4.5:1"
    f.focus(start)
    seen, bad = _tab_all(page, f)
    assert len(seen) >= 3, seen
    assert not bad, bad
    page.close()


def test_overlay_is_an_alert_with_a_name(ui_server, browser):
    page = browser.new_page()
    r = Replay(page, ui_server, "s1_government")
    r.until(is_danger)
    r.one()
    snap = page.accessibility.snapshot(root=r.frame.query_selector("#overlay")) if hasattr(page, "accessibility") else None
    role = r.frame.get_attribute("#overlay", "role")
    name = r.frame.inner_text("#ov-h")
    assert role == "alertdialog" and name == "Scam detected"
    if snap:
        assert snap.get("role") == "alertdialog"
    page.close()
