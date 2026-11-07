"""Shared fixtures for the UI browser tests (skip cleanly without Playwright/Chromium)."""
import functools
import os
import http.server
import pathlib
import threading

import pytest

UI = pathlib.Path(__file__).resolve().parents[2] / "ui"


@pytest.fixture(scope="module")
def ui_server():
    handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(UI))
    handler.log_message = lambda *a, **k: None
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield f"http://127.0.0.1:{srv.server_address[1]}"
    srv.shutdown()


@pytest.fixture(scope="module")
def browser():
    sync_api = pytest.importorskip("playwright.sync_api")
    with sync_api.sync_playwright() as pw:
        try:
            # CALLGUARD_CHROMIUM: optional path to a Chromium build when Playwright's own is missing.
            b = pw.chromium.launch(executable_path=os.environ.get("CALLGUARD_CHROMIUM") or None)
        except Exception as e:  # no browser build installed
            pytest.skip(f"no Chromium: {e}")
        yield b
        b.close()
