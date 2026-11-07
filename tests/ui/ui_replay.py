"""Drive ui/dev/replay.html from Python Playwright (shared by the UI browser tests)."""
import json
import pathlib
import re

FIXTURES = pathlib.Path(__file__).resolve().parents[2] / "ui" / "dev" / "fixtures"


def _steps(name):
    return [s["msg"] for s in json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))["steps"]]


class Replay:
    def __init__(self, page, ui_server, name):
        self.page = page
        self.steps = _steps(name)
        page.goto(f"{ui_server}/dev/replay.html?f={name}&autoplay=0")
        page.wait_for_function("!document.getElementById('clock').textContent.includes('waiting')")
        self.frame = page.frame(url=re.compile(r"index\.html"))
        # Capture every UI -> Server message the harness receives.
        page.evaluate(
            """() => { const h = window.callguardReplay; const orig = h.received.bind(h);
            window.__sent = []; h.received = (m) => { window.__sent.push(m); orig(m); }; }"""
        )
        self.frame.evaluate(
            """() => { window.__tones = 0; const O = window.AudioContext;
            window.AudioContext = class extends O { createOscillator() { window.__tones++; return super.createOscillator(); } }; }"""
        )

    def next_index(self):
        t = self.page.text_content("#fed-n")
        return int(t.split("/")[0]) if t else 0

    def until(self, pred):
        """Deliver until the next message matches pred (not delivered). False at the end."""
        while self.next_index() < len(self.steps) and not pred(self.steps[self.next_index()]):
            self.page.click("#step")
        return self.next_index() < len(self.steps)

    def one(self):
        if not self.page.locator("#step").is_disabled():
            self.page.click("#step")


    def sent(self):
        return self.page.evaluate("window.__sent")

    def hold_safe(self, ms, text="SAFE"):
        """Type into the SAFE box, then hold Space on the hold button for `ms`."""
        self.frame.fill("#safe-input", text)
        self.frame.focus("#safe-hold")
        self.page.keyboard.down(" ")
        self.page.wait_for_timeout(ms)
        self.page.keyboard.up(" ")

    def mark_safe(self):
        self.hold_safe(3300)


def is_danger(m):
    return m["type"] == "check" and m["data"].get("risk") == "danger"


def is_end(m):
    return m["type"] == "call" and m["data"]["state"] == "ended"


def is_gate_locked(m):
    return m["type"] == "gate" and m["data"].get("state") == "locked"
