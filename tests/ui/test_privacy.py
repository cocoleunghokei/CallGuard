"""UI-7 privacy: no transcript persists, is logged, or survives call end.

Static checks always run. The browser check replays every call fixture and
looks for transcript text in the DOM after `call ended`; it skips cleanly when
Python Playwright or a Chromium build is not installed.
"""
import json
import pathlib
import re

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
UI = ROOT / "ui"
APP_FILES = [UI / "index.html", *sorted(UI.glob("*.js"))]
ALL_UI = sorted(p for p in UI.rglob("*") if p.suffix in {".js", ".html", ".css"})

STORAGE = re.compile(r"\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b")
CONSOLE = re.compile(r"\bconsole\.\w+\s*\(")
EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""")


@pytest.mark.parametrize("path", APP_FILES, ids=lambda p: p.name)
def test_no_browser_storage(path):
    assert not STORAGE.search(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("path", ALL_UI, ids=lambda p: str(p.relative_to(UI)))
def test_console_only_with_last_80_chars(path):
    for line in path.read_text(encoding="utf-8").splitlines():
        if CONSOLE.search(line):
            assert ".slice(-80)" in line, f"console call without .slice(-80): {line.strip()}"


@pytest.mark.parametrize("path", ALL_UI, ids=lambda p: str(p.relative_to(UI)))
def test_no_external_assets(path):
    assert not EXTERNAL.search(path.read_text(encoding="utf-8")), "must work with Wi-Fi off"


def test_ws_default_is_localhost():
    assert "ws://localhost:8000/ws" in (UI / "ws.js").read_text(encoding="utf-8")


def test_tail_is_capped_and_wiped():
    app = (UI / "app.js").read_text(encoding="utf-8")
    assert "const TAIL_LINES = 3;" in app
    assert re.search(r"function wipeCall\(\) \{[^}]*state\.tail\.length = 0;[^}]*state\.check = null;", app, re.S)


# ---------------------------------------------------------------- browser check

CALL_FIXTURES = sorted(p.stem for p in (UI / "dev" / "fixtures").glob("*.json") if p.stem != "idle")


@pytest.mark.parametrize("name", CALL_FIXTURES)
def test_transcript_gone_from_dom_after_call_end(name, ui_server, browser):
    fixture = json.loads((UI / "dev" / "fixtures" / f"{name}.json").read_text(encoding="utf-8"))
    texts = [s["msg"]["data"]["text"] for s in fixture["steps"] if s["msg"]["type"] == "transcript"]
    quotes = [e["quote"] for s in fixture["steps"] if s["msg"]["type"] == "check" for e in s["msg"]["data"].get("evidence", [])]

    page = browser.new_page()
    page.goto(f"{ui_server}/dev/replay.html?f={name}&autoplay=0")
    page.wait_for_function("!document.getElementById('clock').textContent.includes('waiting')")
    seen_during_call = False
    while not page.locator("#step").is_disabled():
        page.click("#step")
        frame = page.frame(url=re.compile(r"index\.html"))
        if not seen_during_call and texts:
            seen_during_call = any(t in frame.evaluate("document.body.innerText") for t in texts)
    frame = page.frame(url=re.compile(r"index\.html"))
    html = frame.evaluate("document.documentElement.outerHTML")
    page.close()

    assert seen_during_call, "transcript never rendered; the check would prove nothing"
    for t in texts + quotes:
        assert t not in html, f"left in DOM after call end: {t[-80:]!r}"
