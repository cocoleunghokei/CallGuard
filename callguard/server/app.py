"""SRV-1: FastAPI app. Serves ui/ statically and the WebSocket at /ws.

Every Server -> UI message is {"type": ..., "data": ...} (root AGENTS.md section 3).
UI -> Server messages are dispatched by "type" to handlers registered on the Hub.
Message contents are never logged: only the type.
"""
from __future__ import annotations

import asyncio
import logging
from pathlib import Path
from typing import Any, Awaitable, Callable

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from callguard.server import egress
from callguard.shared.contracts import ClientMessageType, MessageType

log = logging.getLogger("callguard.server")

UI_DIR = Path(__file__).resolve().parents[2] / "ui"
SERVER_TYPES: frozenset[str] = frozenset(MessageType.__args__)  # type: ignore[attr-defined]
CLIENT_TYPES: frozenset[str] = frozenset(ClientMessageType.__args__)  # type: ignore[attr-defined]

PLACEHOLDER_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Callguard</title></head>
<body style="font-family:-apple-system,sans-serif;padding:16px">
<h1>Callguard</h1>
<p>The server is running. The UI (<code>ui/index.html</code>) is not in place yet.</p>
<p>WebSocket: <code>ws://localhost:8000/ws</code></p>
</body></html>"""

ClientHandler = Callable[[dict], Awaitable[None] | None]
ConnectHook = Callable[[WebSocket], Awaitable[None]]


class Hub:
    """Connected WebSocket clients, broadcast, and client-message dispatch."""

    def __init__(self) -> None:
        self.clients: set[WebSocket] = set()
        self.handlers: dict[str, ClientHandler] = {}
        self.on_connect: list[ConnectHook] = []
        self.loop: asyncio.AbstractEventLoop | None = None

    def handle(self, msg_type: str, fn: ClientHandler) -> None:
        if msg_type not in CLIENT_TYPES:
            raise ValueError(f"unknown client message type: {msg_type}")
        self.handlers[msg_type] = fn

    @staticmethod
    def message(msg_type: str, data: Any, **extra: Any) -> dict:
        if msg_type not in SERVER_TYPES:
            raise ValueError(f"unknown server message type: {msg_type}")
        return {"type": msg_type, "data": data, **extra}

    async def send(self, ws: WebSocket, msg_type: str, data: Any, **extra: Any) -> None:
        await ws.send_json(self.message(msg_type, data, **extra))

    async def broadcast(self, msg_type: str, data: Any, **extra: Any) -> None:
        msg = self.message(msg_type, data, **extra)
        dead = []
        for ws in list(self.clients):
            try:
                await ws.send_json(msg)
            except Exception:
                dead.append(ws)
        for ws in dead:
            self.clients.discard(ws)

    def broadcast_threadsafe(self, msg_type: str, data: Any, **extra: Any) -> None:
        """Broadcast from a worker thread (e.g. egress, detection)."""
        self.message(msg_type, data, **extra)  # validate type in the caller's thread
        if self.loop is None or self.loop.is_closed():
            return
        asyncio.run_coroutine_threadsafe(self.broadcast(msg_type, data, **extra), self.loop)

    async def dispatch(self, msg: Any) -> None:
        if not isinstance(msg, dict) or msg.get("type") not in CLIENT_TYPES:
            log.warning("ignored client message (bad type)")
            return
        fn = self.handlers.get(msg["type"])
        if fn is None:
            log.info("client message %s: no handler yet", msg["type"])
            return
        result = fn(msg)
        if asyncio.iscoroutine(result):
            await result


def create_app(hub: Hub | None = None, ui_dir: Path = UI_DIR) -> FastAPI:
    hub = hub or Hub()
    app = FastAPI(title="Callguard", docs_url=None, redoc_url=None, openapi_url=None)
    app.state.hub = hub

    # Every egress entry goes to the UI; a (re)connecting UI gets the log so far.
    egress.subscribe(lambda entry: hub.broadcast_threadsafe("egress", entry))

    async def send_egress_log(ws: WebSocket) -> None:
        for entry in list(egress.entries):
            await hub.send(ws, "egress", entry)

    hub.on_connect.insert(0, send_egress_log)

    @app.websocket("/ws")
    async def ws_endpoint(ws: WebSocket) -> None:
        await ws.accept()
        hub.loop = asyncio.get_running_loop()
        hub.clients.add(ws)
        try:
            for hook in hub.on_connect:
                await hook(ws)
            while True:
                try:
                    msg = await ws.receive_json()
                except (ValueError, KeyError):
                    log.warning("ignored client message (not JSON)")
                    continue
                await hub.dispatch(msg)
        except WebSocketDisconnect:
            pass
        finally:
            hub.clients.discard(ws)

    if (ui_dir / "index.html").is_file():
        app.mount("/", StaticFiles(directory=ui_dir, html=True), name="ui")
    else:
        @app.get("/", response_class=HTMLResponse)
        async def placeholder() -> str:
            return PLACEHOLDER_HTML

    return app
