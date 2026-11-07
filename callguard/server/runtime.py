"""Glue: one Hub (WebSocket) + one Pipeline, and the UI messages that drive them."""
from __future__ import annotations

import logging
from pathlib import Path

from fastapi import WebSocket

from callguard.server.app import Hub
from callguard.server.pipeline import Pipeline

log = logging.getLogger("callguard.server")


class Runtime:
    def __init__(self, hub: Hub, pipeline: Pipeline | None = None) -> None:
        self.hub = hub
        self.pipeline = pipeline or Pipeline(hub.broadcast)
        hub.handle("end_call", self._on_end_call)
        hub.handle("mark_safe", self._on_mark_safe)
        hub.on_connect.append(self._hello)

    async def _hello(self, ws: WebSocket) -> None:
        await self.hub.send(ws, "rules", self.pipeline.rules, source="default")
        if self.pipeline.active:
            await self.hub.send(ws, "call", {"state": "started"})
            if self.pipeline.call_risk.shown:
                await self.hub.send(ws, "check", self.pipeline.call_risk.shown)

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
        await self.pipeline.run_fake(script, speed=speed)

    def close(self) -> None:
        self.pipeline.close()
