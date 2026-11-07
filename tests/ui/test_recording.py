"""T9: the backup-video recording mode of the replay harness (documented in dev/replay.html)."""
import pathlib
import re

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


def test_recording_mode_is_documented_in_the_harness():
    html = (UI / "dev" / "replay.html").read_text(encoding="utf-8")
    url = re.search(r"\?clean=1&f=([\w,]+)&exit=hang_up", html)
    assert url, "replay.html must document the hands-free recording URL"
    for name in url.group(1).split(","):
        assert (UI / "dev" / "fixtures" / f"{name}.json").exists(), name


def test_clean_playlist_and_auto_exit(ui_server, browser):
    page = browser.new_page()
    page.goto(f"{ui_server}/dev/replay.html?clean=1&f=s1_government,offline&exit=hang_up&exit_after=0.5&speed=4&gap=1")
    page.evaluate(
        """() => { const h = window.callguardReplay; const orig = h.received.bind(h);
        window.__sent = []; h.received = (m) => { window.__sent.push(m); orig(m); }; }"""
    )
    assert page.evaluate("getComputedStyle(document.querySelector('.side')).display") == "none"
    page.wait_for_function("window.__sent.length >= 1", timeout=20000)
    assert page.evaluate("window.__sent[0]") == {"type": "gate_release", "how": "hang_up"}
    page.wait_for_function("document.getElementById('fixture').value === 'offline'", timeout=20000)
    page.close()
