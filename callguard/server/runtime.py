"""Glue: one Hub (WebSocket) + one Pipeline, and the UI messages that drive them."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from pathlib import Path
from typing import Callable, Iterable

from fastapi import WebSocket

from callguard.server import egress
from callguard.server.app import Hub
from callguard.server.gate import SoftGate
from callguard.server.pipeline import Pipeline
from callguard.server.verify import Verifier
from callguard.server.window import notify_colleague_macos
from callguard.shared.contracts import Status

STATUS_EVERY_S = 15.0  # C16
AUDIO_RETRY_S = 10.0  # live audio: try the devices again after a failure
COLLEAGUE_DEDUPE_S = 5.0  # the UI sends `colleague` and `gate_release{colleague}` together

log = logging.getLogger("callguard.server")


class Runtime:
    def __init__(self, hub: Hub, pipeline: Pipeline | None = None) -> None:
        self.hub = hub
        self.pipeline = pipeline or Pipeline(hub.broadcast)
        hub.handle("end_call", self._on_end_call)
        hub.handle("mark_safe", self._on_mark_safe)
        hub.handle("colleague", self._on_colleague)
        hub.handle("gate_release", self._on_gate_release)
        hub.handle("save_rules", self._on_save_rules)
        hub.handle("reset_rules", self._on_reset_rules)
        hub.on_connect.append(self._hello)
        p = self.pipeline
        self.verifier = Verifier(hub.broadcast, p.caller_lines, lambda: p.call_id)
        p.on_check.append(self.verifier)
        p.on_stream_end.append(self.verifier.drain)
        p.on_call_end.append(self.verifier.reset)
        self.gate = SoftGate(hub.broadcast)
        p.on_check.append(self.gate.on_check)
        p.on_call_end.append(self.gate.reset)
        p.on_check.append(self._model_from_check)
        self.listening = False
        self.online = False
        self.model: str | None = None  # "ok" | "degraded", once a check has run
        self.audio: tuple[bool, str] | None = None  # live mode only: (ok, plain message)
        self._colleague_at = 0.0

    # ------------------------------------------------------------ status (SRV-6)
    @staticmethod
    def gate_mode() -> str:
        return "off" if os.environ.get("CALLGUARD_GATE", "on").strip().lower() == "off" else "on"

    def status(self) -> Status:
        s: dict = {"listening": self.listening, "online": self.online, "gate": self.gate_mode()}
        if self.model:
            s["model"] = self.model
        if self.audio is not None:
            s["audio_ok"], s["audio_message"] = self.audio
        return s  # type: ignore[return-value]

    async def _model_from_check(self, raw: dict, _shown: dict) -> None:
        """C15: a `fallback` check means the local model didn't answer."""
        # "fast" = the model didn't answer, only the firm's cue phrases were checked
        model = "degraded" if raw.get("source") in ("fallback", "fast") else "ok"
        if model != self.model:
            self.model = model
            log.info("local model %s", model)
            await self.push_status()

    async def set_audio(self, ok: bool, message: str) -> None:
        if self.audio != (ok, message):
            self.audio = (ok, message)
            await self.push_status()

    async def push_status(self) -> None:
        await self.hub.broadcast("status", self.status())

    async def refresh_online(self) -> None:
        online = await asyncio.to_thread(egress.online, True)
        if online != self.online:
            self.online = online
            log.info("network %s", "online" if online else "offline")
            await self.push_status()

    async def status_loop(self, _hub: Hub | None = None) -> None:
        """Background task: probe the network every 15 s, push `status` on change."""
        while True:
            await self.refresh_online()
            await asyncio.sleep(STATUS_EVERY_S)

    async def set_listening(self, listening: bool) -> None:
        if listening != self.listening:
            self.listening = listening
            await self.push_status()

    # ------------------------------------------------------------ connect + UI messages
    async def _hello(self, ws: WebSocket) -> None:
        await self.hub.send(ws, "status", self.status())
        await self.hub.send(ws, "rules", self.pipeline.rules, source=self.pipeline.rules_source)
        if self.pipeline.active:
            await self.hub.send(ws, "call", {"state": "started"})
            if self.pipeline.call_risk.shown:
                await self.hub.send(ws, "check", self.pipeline.call_risk.shown)
            for v in list(self.verifier.cache.values()):
                await self.hub.send(ws, "verify", v)
        await self.hub.send(ws, "gate", self.gate.snapshot())

    async def _on_end_call(self, msg: dict) -> None:
        await self.pipeline.end_call()

    async def _on_mark_safe(self, msg: dict) -> None:
        if not self.pipeline.active:
            return
        await self.gate.release("mark_safe")
        shown = self.pipeline.call_risk.act("mark_safe")
        if shown:
            await self.hub.broadcast("check", shown)

    async def _on_colleague(self, msg: dict) -> None:
        if not self.pipeline.active:
            return
        await self.gate.release("colleague")
        self.pipeline.call_risk.act("colleague")
        now = time.monotonic()
        if now - self._colleague_at >= COLLEAGUE_DEDUPE_S:  # one heads-up per tap
            self._colleague_at = now
            notify_colleague_macos()

    async def _on_gate_release(self, msg: dict) -> None:
        how = msg.get("how")
        if not self.pipeline.active or how not in {"hang_up", "colleague", "mark_safe"}:
            return
        if how == "mark_safe":
            await self._on_mark_safe(msg)
        elif how == "colleague":
            await self._on_colleague(msg)
        else:
            await self.gate.release(how)
            self.pipeline.call_risk.act(how)

    # ------------------------------------------------------------ firm rules (SRV-14, cues only)
    async def _on_save_rules(self, msg: dict) -> None:
        """Validate, write the custom file atomically, reload, tell every window.

        Refused during a call: rules never change mid-call, and nothing is
        written to disk while a call is active (SRV-12b). Never an egress entry.
        """
        if self.pipeline.active:
            await self.hub.broadcast("rules_saved", {"ok": False, "errors": [RULES_IN_CALL]})
            return
        from callguard.detection.rules import prepare_rules, validate_rules
        data = prepare_rules(msg.get("data"))
        errors = validate_rules(data)
        if errors:
            await self.hub.broadcast("rules_saved", {"ok": False, "errors": errors})
            return
        try:
            await asyncio.to_thread(_write_rules, data)
        except OSError as e:
            log.warning("saving rules failed: %s", type(e).__name__)
            await self.hub.broadcast("rules_saved", {"ok": False, "errors": ["Couldn't save the rules on this laptop."]})
            return
        await self._reload_rules()
        await self.hub.broadcast("rules_saved", {"ok": True})

    async def _on_reset_rules(self, msg: dict) -> None:
        if self.pipeline.active:
            await self.hub.broadcast("rules_saved", {"ok": False, "errors": [RULES_IN_CALL]})
            return
        from callguard.detection.rules import custom_rules_path
        try:
            custom_rules_path().unlink(missing_ok=True)
        except OSError as e:
            log.warning("resetting rules failed: %s", type(e).__name__)
            await self.hub.broadcast("rules_saved", {"ok": False, "errors": ["Couldn't reset the rules on this laptop."]})
            return
        await self._reload_rules()
        await self.hub.broadcast("rules_saved", {"ok": True})

    async def _reload_rules(self) -> None:
        from callguard.server.pipeline import load_rules_with_source
        p = self.pipeline
        p.rules, p.rules_source = load_rules_with_source()
        log.info("rules reloaded: %d %s", len(p.rules), p.rules_source)
        await self.hub.broadcast("rules", p.rules, source=p.rules_source)

    async def run_fake(self, script: str | Path, speed: float = 1.0) -> None:
        await self.hub.wait_for_client()  # don't play the call to an empty room
        await self.set_listening(True)
        try:
            await self.pipeline.run_fake(script, speed=speed)
        finally:
            await self.set_listening(False)

    async def run_live(self, make_stream: Callable[[], Iterable] | None = None,
                       health: Callable[[], tuple[bool, str]] | None = None,
                       retry_s: float = AUDIO_RETRY_S) -> None:
        """Default mode: listen to the mic + BlackHole while the window is open.

        If the devices aren't ready, say so in `status` and try again every
        `retry_s` seconds instead of crashing.
        """
        make_stream = make_stream or _live_stream
        health = health or _audio_health
        await self.hub.wait_for_client()
        while True:
            ok, message = await asyncio.to_thread(health)
            await self.set_audio(ok, message)
            if ok:
                await self.set_listening(True)
                try:
                    await self.pipeline.run_live(make_stream)
                finally:
                    await self.set_listening(False)
                await self.set_audio(False, "Audio stopped. Check the microphone and BlackHole input.")
            await asyncio.sleep(retry_s)

    def close(self) -> None:
        self.gate.close()
        self.pipeline.close()


RULES_IN_CALL = "Rules can't be changed during a call. Try again after the call ends."


def _write_rules(rules: list) -> None:
    """Atomic write: a crash mid-save never leaves a half-written rules file."""
    from callguard.detection.rules import custom_rules_path
    path = custom_rules_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(rules, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, path)


def _live_stream() -> Iterable:
    from callguard.audio import stream_chunks
    return stream_chunks()


def _audio_health() -> tuple[bool, str]:
    try:
        from callguard.audio import audio_health
        h = audio_health()
        return bool(h.ok), str(h.message)
    except Exception as e:  # numpy / sounddevice / faster-whisper not installed
        log.warning("audio check failed: %s", type(e).__name__)
        return False, "Audio capture is unavailable. Install the audio requirements."
