"""Glue: one Hub (WebSocket) + one Pipeline, and the UI messages that drive them."""
from __future__ import annotations

import asyncio
import logging
import os
from pathlib import Path

from fastapi import WebSocket

from callguard.server import egress
from callguard.server.app import Hub
from callguard.server.pipeline import Pipeline
from callguard.server.verify import Verifier
from callguard.shared.contracts import Status

STATUS_EVERY_S = 15.0  # C16

log = logging.getLogger("callguard.server")


class Runtime:
    def __init__(self, hub: Hub, pipeline: Pipeline | None = None) -> None:
        self.hub = hub
        self.pipeline = pipeline or Pipeline(hub.broadcast)
        hub.handle("end_call", self._on_end_call)
        hub.handle("mark_safe", self._on_mark_safe)
        hub.on_connect.append(self._hello)
        p = self.pipeline
        self.verifier = Verifier(hub.broadcast, p.caller_lines, lambda: p.call_id)
        p.on_check.append(self.verifier)
        p.on_call_end.append(self.verifier.reset)
        self.listening = False
        self.online = False

    # ------------------------------------------------------------ status (SRV-6)
    @staticmethod
    def gate_mode() -> str:
        return "off" if os.environ.get("CALLGUARD_GATE", "on").strip().lower() == "off" else "on"

    def status(self) -> Status:
        return {"listening": self.listening, "online": self.online, "gate": self.gate_mode()}  # type: ignore[typeddict-item]

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
        await self.hub.send(ws, "rules", self.pipeline.rules, source="default")
        if self.pipeline.active:
            await self.hub.send(ws, "call", {"state": "started"})
            if self.pipeline.call_risk.shown:
                await self.hub.send(ws, "check", self.pipeline.call_risk.shown)
            for v in list(self.verifier.cache.values()):
                await self.hub.send(ws, "verify", v)

    async def _on_end_call(self, msg: dict) -> None:
        await self.pipeline.end_call()

    async def _on_mark_safe(self, msg: dict) -> None:
        if not self.pipeline.active:
            return
        shown = self.pipeline.call_risk.act("mark_safe")
        if shown:
            await self.hub.broadcast("check", shown)

    async def run_fake(self, script: str | Path, speed: float = 1.0) -> None:
        await self.hub.wait_for_client()  # don't play the call to an empty room
        await self.set_listening(True)
        try:
            await self.pipeline.run_fake(script, speed=speed)
        finally:
            await self.set_listening(False)

    def close(self) -> None:
        self.pipeline.close()
