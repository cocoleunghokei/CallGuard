"""SRV-5 via the WebSocket: end_call and mark_safe from the UI."""
import threading

from fastapi.testclient import TestClient

from callguard.server.app import Hub, create_app
from callguard.server.pipeline import Pipeline
from callguard.server.runtime import Runtime

DANGER = {"risk": "danger", "tactics": ["secrecy", "bank_change"], "claimed_identity": None,
          "rules_broken": [], "reason": "r", "next_step": "n", "confidence": 0.99}


def make(tmp_path, chunks, check=lambda w, r: DANGER):
    hub = Hub()
    rt = Runtime(hub, Pipeline(hub.broadcast, check_fn=check, rules=[]))
    gate = threading.Event()

    def stream():
        for c in chunks:
            yield c
        gate.wait(5)  # hold the call open until the test is done

    async def task(_hub):
        await rt.pipeline.run(stream())

    return TestClient(create_app(hub, ui_dir=tmp_path, tasks=[task])), rt, gate


def ch(text, start):
    return {"speaker": "caller", "text": text, "start": start, "end": start + 3, "language": "en"}


def next_of(ws, t):
    while True:
        m = ws.receive_json()
        if m["type"] == t:
            return m


def test_end_call_from_ui_clears_memory(tmp_path):
    client, rt, gate = make(tmp_path, [ch("do not tell anyone", 0)])
    with client, client.websocket_connect("/ws") as ws:
        assert next_of(ws, "check")["data"]["risk"] == "danger"
        ws.send_json({"type": "end_call"})
        assert next_of(ws, "call")["data"] == {"state": "ended"}
        assert len(rt.pipeline.window) == 0 and rt.pipeline.call_risk.shown is None
        gate.set()


def test_mark_safe_from_ui_lowers_risk(tmp_path):
    client, rt, gate = make(tmp_path, [ch("do not tell anyone", 0)])
    with client, client.websocket_connect("/ws") as ws:
        assert next_of(ws, "check")["data"]["risk"] == "danger"
        ws.send_json({"type": "mark_safe"})
        assert next_of(ws, "check")["data"]["risk"] == "low"
        gate.set()


def test_reconnecting_ui_gets_call_state(tmp_path):
    client, rt, gate = make(tmp_path, [ch("do not tell anyone", 0)])
    with client:
        with client.websocket_connect("/ws") as ws:
            next_of(ws, "check")
        with client.websocket_connect("/ws") as ws2:
            assert ws2.receive_json() == {"type": "rules", "data": [], "source": "default"}
            assert ws2.receive_json() == {"type": "call", "data": {"state": "started"}}
            assert ws2.receive_json()["data"]["risk"] == "danger"
        gate.set()
