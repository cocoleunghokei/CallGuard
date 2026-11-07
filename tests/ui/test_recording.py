"""T9: the backup-video recording mode of the replay harness (ui/DEMO.md §6)."""
import pathlib
import re

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


def test_demo_md_recording_url_uses_real_fixtures():
    demo = (UI / "DEMO.md").read_text(encoding="utf-8")
    url = re.search(r"replay\.html\?clean=1&f=([\w,]+)&exit=hang_up", demo)
    assert url, "DEMO.md must give the hands-free recording URL"
    for name in url.group(1).split(","):
        assert (UI / "dev" / "fixtures" / f"{name}.json").exists(), name


def test_demo_md_script_path_exists():
    demo = (UI / "DEMO.md").read_text(encoding="utf-8")
    for path in re.findall(r"--fake (\S+\.txt)", demo):
        assert (UI.parent / path).exists(), path


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
