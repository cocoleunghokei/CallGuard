"""Static privacy checks on the UI source (lane rules + AGENTS.md guardrails 1, 2)."""
import pathlib
import re

import pytest

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"
SOURCES = sorted(p for p in UI.rglob("*") if p.suffix in {".js", ".html", ".css"})

STORAGE = re.compile(r"\b(localStorage|sessionStorage|indexedDB|document\.cookie)\b")
CONSOLE = re.compile(r"\bconsole\.(log|info|debug|warn|error)\b")
EXTERNAL = re.compile(r"""(?:src|href)\s*=\s*["'](?:https?:)?//""")


@pytest.mark.parametrize("path", SOURCES, ids=lambda p: str(p.relative_to(UI)))
def test_no_storage_console_or_external_assets(path):
    text = path.read_text(encoding="utf-8")
    assert not STORAGE.search(text), "no browser storage: transcript must never persist"
    assert not CONSOLE.search(text), "no console output from UI code"
    assert not EXTERNAL.search(text), "no CDN or external assets: must work with Wi-Fi off"


def test_ws_default_is_localhost():
    assert 'ws://localhost:8000/ws' in (UI / "ws.js").read_text(encoding="utf-8")
