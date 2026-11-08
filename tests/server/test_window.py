"""SRV-11: window mode with a fake pywebview; danger alert copy and no re-nagging."""
import socket as _socket_for_free_port  # tests may use sockets; the AST scan covers callguard/ only
import sys
import threading
import types
import urllib.request

import pytest

from callguard.server import window
from callguard.server.__main__ import build_app, main, parse_args


def danger(*tactics, conf=0.99):
    return {"risk": "danger", "tactics": list(tactics), "claimed_identity": "Department of Justice",
            "rules_broken": [], "reason": "caller words here", "next_step": "", "confidence": conf}


def test_window_module_does_not_import_pywebview():
    assert "webview" not in sys.modules


def test_alert_once_then_only_for_new_ask():
    fronts, bodies = [], []
    a = window.DangerAlert(lambda: fronts.append(1), bodies.append)
    a(danger("secrecy"), danger("secrecy"))
    a(danger("secrecy"), danger("secrecy"))                   # same: no re-nag
    a({"risk": "low", "tactics": []}, danger("secrecy"))      # sticky danger, nothing new
    a(danger("bank_change"), danger("bank_change"))           # new ask
    a(danger("bank_change"), danger("bank_change"))
    assert len(fronts) == 2
    assert bodies == [window.NOTIFY_DEFAULT, "The caller is asking for bank details. Click for details."]
    a.reset()
    a(danger("bank_change"), danger("bank_change"))
    assert len(fronts) == 3


def test_alert_ignores_non_danger():
    calls = []
    a = window.DangerAlert(lambda: calls.append(1), calls.append)
    a({"risk": "watch", "tactics": ["bank_change"]}, {"risk": "watch", "tactics": ["bank_change"]})
    assert calls == []


def test_notification_never_carries_call_content(monkeypatch):
    ran = []
    monkeypatch.setattr(window.sys, "platform", "darwin")
    monkeypatch.setattr(window.shutil, "which", lambda n: "/usr/bin/osascript")
    monkeypatch.setattr(window.subprocess, "Popen", lambda cmd, **k: ran.append(cmd))
    a = window.DangerAlert(lambda: None)
    a(danger("credential_request"), danger("credential_request"))
    script = ran[0][2]
    assert window.NOTIFY_TITLE in script and "code or password" in script
    assert "Department of Justice" not in script and "caller words" not in script
    with pytest.raises(ValueError):
        window.notify_macos("Officer Chen says hi")


def test_notify_is_noop_off_mac(monkeypatch):
    monkeypatch.setattr(window.sys, "platform", "linux")
    monkeypatch.setattr(window.subprocess, "Popen", lambda *a, **k: pytest.fail("ran osascript"))
    window.notify_macos(window.NOTIFY_DEFAULT)


def test_colleague_notification_is_fixed_and_local(monkeypatch):
    ran = []
    monkeypatch.setattr(window.sys, "platform", "darwin")
    monkeypatch.setattr(window.shutil, "which", lambda n: "/usr/bin/osascript")
    monkeypatch.setattr(window.subprocess, "Popen", lambda cmd, **kw: ran.append((cmd, kw)))
    window.notify_colleague_macos()
    command, kwargs = ran[0]
    assert command[:2] == ["osascript", "-e"]
    assert window.COLLEAGUE_BODY in command[2]
    assert window.COLLEAGUE_TITLE in command[2]
    assert "caller words" not in command[2] and "Department of Justice" not in command[2]
    assert kwargs["stdout"] == window.subprocess.DEVNULL


def test_colleague_notification_is_noop_off_mac(monkeypatch):
    monkeypatch.setattr(window.sys, "platform", "linux")
    monkeypatch.setattr(window.subprocess, "Popen", lambda *a, **k: pytest.fail("ran osascript"))
    window.notify_colleague_macos()


def free_port():
    with _socket_for_free_port.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def test_run_window_serves_in_a_thread_and_opens_on_top(monkeypatch):
    opened = {}

    class FakeWindow:
        def restore(self): opened["restored"] = True
        def show(self): opened["shown"] = True

    def create_window(title, url, **kw):
        opened.update(title=title, url=url, **kw)
        return FakeWindow()

    def start():
        opened["main_thread"] = threading.current_thread() is threading.main_thread()
        with urllib.request.urlopen(opened["url"], timeout=5) as r:  # server is up while the window is open
            opened["status"] = r.status

    monkeypatch.setitem(sys.modules, "webview", types.SimpleNamespace(create_window=create_window, start=start))
    port = free_port()
    app, runtime = build_app(parse_args(["--port", str(port), "--no-audio"]))
    window.run_window(app, runtime, "127.0.0.1", port)
    assert opened["title"] == "Callguard" and opened["on_top"] is True
    assert opened["width"] <= 420 and opened["main_thread"] and opened["status"] == 200
    assert any(isinstance(h, window.DangerAlert) for h in runtime.pipeline.on_check)
    runtime.pipeline.on_check[-1](danger("bank_change"), danger("bank_change"))
    assert opened.get("shown")
    runtime.close()


def test_default_mode_uses_window_and_browser_does_not(monkeypatch):
    used = []
    monkeypatch.setattr(window, "run_window", lambda *a, **k: used.append("window"))
    monkeypatch.setattr("callguard.server.__main__.uvicorn.run", lambda *a, **k: used.append("uvicorn"))
    main(["--port", "1"])
    main(["--browser", "--port", "1"])
    assert used == ["window", "uvicorn"]


def test_missing_pywebview_says_how_to_fix(monkeypatch):
    monkeypatch.setitem(sys.modules, "webview", None)
    with pytest.raises(SystemExit, match="pywebview"):
        window.import_webview()


def test_inside_callguard_app_posts_natively_not_osascript(monkeypatch):
    posted = []
    monkeypatch.setattr(window, "_post_native", lambda t, b: posted.append((t, b)) or True)
    monkeypatch.setattr(window.subprocess, "Popen", lambda *a, **k: pytest.fail("ran osascript"))
    window.notify_macos(window.NOTIFY_DEFAULT)
    window.notify_colleague_macos()
    assert posted == [(window.NOTIFY_TITLE, window.NOTIFY_DEFAULT),
                      (window.COLLEAGUE_TITLE, window.COLLEAGUE_BODY)]


def test_fixed_copy_is_checked_before_any_native_post(monkeypatch):
    monkeypatch.setattr(window, "_post_native", lambda t, b: pytest.fail("posted"))
    with pytest.raises(ValueError):
        window.notify_macos("Officer Chen says hi")


def test_outside_the_app_falls_back_to_osascript(monkeypatch):
    ran = []
    monkeypatch.setattr(window.sys, "platform", "darwin")
    monkeypatch.setattr(window, "_post_native", lambda t, b: False)
    monkeypatch.setattr(window.shutil, "which", lambda n: "/usr/bin/osascript")
    monkeypatch.setattr(window.subprocess, "Popen", lambda cmd, **k: ran.append(cmd))
    window.notify_macos(window.NOTIFY_DEFAULT)
    assert ran and window.NOTIFY_DEFAULT in ran[0][2]


def test_native_post_is_off_without_the_app_bundle(monkeypatch):
    monkeypatch.setattr(window.sys, "platform", "linux")
    assert window._post_native(window.NOTIFY_TITLE, window.NOTIFY_DEFAULT) is False


def test_notification_click_brings_the_window_back(monkeypatch):
    clicks = []
    monkeypatch.setattr(window, "_on_click", lambda: clicks.append(1))
    window._clicked()
    assert clicks == [1]


def test_mac_app_recipe_matches_the_notification_bundle_id():
    from pathlib import Path
    macapp = Path(window.__file__).parent / "macapp"
    assert f'"{window.BUNDLE_ID}"' in (macapp / "setup.py").read_text()
    assert (macapp / "Callguard.icns").stat().st_size > 0
    assert "NSMicrophoneUsageDescription" in (macapp / "setup.py").read_text()
