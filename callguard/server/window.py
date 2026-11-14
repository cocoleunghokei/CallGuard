"""SRV-11: the native Callguard window (default for `python -m callguard.server`).

pywebview needs the main thread on macOS, so uvicorn runs in a background
thread and the window runs on the main thread. The window is titled
"Callguard", narrow, always on top, and comes to the front on danger (never
full-screen). Nothing here hooks the keyboard or mouse.

The web Notification API is not available inside the native window, so on
danger the server posts the macOS notification itself, using FIXED copy only (macOS keeps notification history on disk: never the
caller's words, a name or a number). Once when the call first reaches danger,
then only for a new ask tactic in the same call.

Run as Callguard.app (callguard/server/macapp/build.sh), the notification is
posted natively: it shows the Callguard icon and clicking it brings the window
back. Run as plain `python -m callguard.server`, it falls back to `osascript`,
which macOS shows as coming from Script Editor.

pywebview and AppKit are imported lazily so pytest runs on Linux without them.
"""
from __future__ import annotations

import logging
import shutil
import subprocess
import sys
import threading
import time
from typing import Any, Callable

import uvicorn

from callguard.server.callrisk import ASK_TACTICS, asks
from callguard.shared.contracts import ScamCheck

log = logging.getLogger("callguard.server.window")

TITLE = "CallGuard"
WIDTH, HEIGHT = 400, 760
MIN_SIZE = (340, 520)

NOTIFY_TITLE = "CallGuard: verify this call before you act"
NOTIFY_BODY = {  # fixed copy, chosen by the ask tactic (prd §9.5)
    "bank_change": "The caller is asking for bank details. Click for details.",
    "credential_request": "The caller is asking for a code or password. Click for details.",
    "payment_request": "The caller is asking you to send money. Click for details.",
    "remote_access": "The caller is asking for access to your computer. Click for details.",
    "personal_data_request": "The caller is asking for personal or client data. Click for details.",
    "bypass_approval": "The caller wants you to skip the usual approval. Click for details.",
}
NOTIFY_DEFAULT = "This call shows signs of a scam. Click for details."
COLLEAGUE_TITLE = "CallGuard: check with a colleague"
COLLEAGUE_BODY = "Heads-up from CallGuard: a call looks suspicious, can you check in?"
ASK_PRIORITY = ("bank_change", "credential_request", "payment_request",
                "remote_access", "personal_data_request", "bypass_approval")
assert set(ASK_PRIORITY) == ASK_TACTICS


def notification_body(ask_tactics: set[str]) -> str:
    for t in ASK_PRIORITY:
        if t in ask_tactics:
            return NOTIFY_BODY[t]
    return NOTIFY_DEFAULT


BUNDLE_ID = "com.hack1984.callguard"  # keep in sync with macapp/setup.py
_on_click: Callable[[], None] | None = None  # set by run_window: bring the window back
_native: Any = None  # (center, delegate) once set up; the delegate must stay referenced


def _clicked() -> None:
    if _on_click is not None:
        try:
            _on_click()
        except Exception as e:
            log.warning("notification click failed: %s", type(e).__name__)


def _deliver_native(title: str, body: str) -> None:
    """Main thread only. Post through the app's own notification center."""
    global _native
    import objc  # type: ignore[import-not-found]
    from Foundation import NSObject, NSUserNotification, NSUserNotificationCenter  # type: ignore[import-not-found]
    if _native is None:
        class CallguardNotificationDelegate(NSObject):
            @objc.typedSelector(b"Z@:@@")
            def userNotificationCenter_shouldPresentNotification_(self, center, note):
                return True  # show the banner even though Callguard is the front app

            @objc.typedSelector(b"v@:@@")
            def userNotificationCenter_didActivateNotification_(self, center, note):
                _clicked()

        center = NSUserNotificationCenter.defaultUserNotificationCenter()
        delegate = CallguardNotificationDelegate.alloc().init()
        center.setDelegate_(delegate)
        _native = (center, delegate)
    note = NSUserNotification.alloc().init()
    note.setTitle_(title)
    note.setInformativeText_(body)
    note.setSoundName_("Sosumi")
    _native[0].deliverNotification_(note)


def _post_native(title: str, body: str) -> bool:
    """True if posted as Callguard.app; False when not running from the app bundle."""
    if sys.platform != "darwin":
        return False
    try:
        from Foundation import NSBundle  # type: ignore[import-not-found]
        from PyObjCTools import AppHelper  # type: ignore[import-not-found]
        if NSBundle.mainBundle().bundleIdentifier() != BUNDLE_ID:
            return False
        AppHelper.callAfter(_deliver_native, title, body)
        return True
    except Exception as e:
        log.warning("native notification unavailable: %s", type(e).__name__)
        return False


def _post_osascript(title: str, body: str) -> None:
    if sys.platform != "darwin" or not shutil.which("osascript"):
        return
    script = f'display notification "{body}" with title "{title}" sound name "Sosumi"'
    try:
        subprocess.Popen(["osascript", "-e", script],
                         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except OSError as e:
        log.warning("notification failed: %s", type(e).__name__)


def notify_macos(body: str) -> None:
    """Post a macOS notification with a sound. `body` must be fixed copy."""
    if body not in NOTIFY_BODY.values() and body != NOTIFY_DEFAULT:
        raise ValueError("notification text must be fixed copy")
    if not _post_native(NOTIFY_TITLE, body):
        _post_osascript(NOTIFY_TITLE, body)


def notify_colleague_macos() -> None:
    """Local P0 heads-up with fixed copy; no transcript, identity, or contact data."""
    if not _post_native(COLLEAGUE_TITLE, COLLEAGUE_BODY):
        _post_osascript(COLLEAGUE_TITLE, COLLEAGUE_BODY)


class DangerAlert:
    """Pipeline hook: bring the window forward + notify, without re-nagging."""

    def __init__(self, bring_to_front: Callable[[], None],
                 notify: Callable[[str], None] = notify_macos) -> None:
        self.bring_to_front = bring_to_front
        self.notify = notify
        self.alerted = False
        self.alerted_asks: set[str] = set()

    def reset(self) -> None:
        self.alerted = False
        self.alerted_asks = set()

    def __call__(self, raw: ScamCheck, shown: ScamCheck) -> None:
        if shown.get("risk") != "danger":
            return
        current = asks(shown) | (asks(raw) if raw.get("risk") == "danger" else set())
        new = current - self.alerted_asks
        if self.alerted and not new:
            return
        self.alerted = True
        self.alerted_asks |= current
        try:
            self.bring_to_front()
        except Exception as e:
            log.warning("bring to front failed: %s", type(e).__name__)
        self.notify(notification_body(new or current))


class ServerThread:
    """uvicorn in a background thread."""

    def __init__(self, app: Any, host: str, port: int) -> None:
        self.server = uvicorn.Server(uvicorn.Config(app, host=host, port=port, log_level="warning"))
        self.thread = threading.Thread(target=self.server.run, name="uvicorn", daemon=True)

    def start(self, timeout: float = 10.0) -> None:
        self.thread.start()
        deadline = time.monotonic() + timeout
        while not self.server.started:
            if not self.thread.is_alive() or time.monotonic() > deadline:
                raise RuntimeError("server did not start (is the port in use?)")
            time.sleep(0.05)

    def stop(self) -> None:
        self.server.should_exit = True
        self.thread.join(timeout=5)


def _activate_app() -> None:
    """Bring Callguard's app to the front on macOS (no-op elsewhere)."""
    if sys.platform != "darwin":
        return
    try:
        from AppKit import NSApplication  # type: ignore[import-not-found]
        from PyObjCTools import AppHelper  # type: ignore[import-not-found]
    except ImportError:
        return
    AppHelper.callAfter(NSApplication.sharedApplication().activateIgnoringOtherApps_, True)


def import_webview():
    try:
        import webview  # type: ignore[import-not-found]
    except ImportError:
        raise SystemExit(
            "The CallGuard window needs pywebview: pip install -r requirements.txt\n"
            "(dev only: python -m callguard.server --browser)") from None
    return webview


def run_window(app: Any, runtime: Any, host: str = "127.0.0.1", port: int = 8000) -> None:
    """Start the server in a thread and the window on this (main) thread. Blocks."""
    webview = import_webview()
    server = ServerThread(app, host, port)
    server.start()
    window = webview.create_window(
        TITLE, f"http://{host}:{port}/", width=WIDTH, height=HEIGHT,
        min_size=MIN_SIZE, on_top=True, resizable=True)

    def bring_to_front() -> None:
        window.restore()  # un-minimise if needed
        window.show()
        _activate_app()

    global _on_click
    _on_click = bring_to_front  # clicking the notification brings the window back
    alert = DangerAlert(bring_to_front)
    runtime.pipeline.on_check.append(alert)
    runtime.pipeline.on_call_end.append(alert.reset)
    try:
        webview.start()  # returns when the window is closed
    finally:
        server.stop()
