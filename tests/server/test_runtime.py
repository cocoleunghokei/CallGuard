"""SRV-5 via the WebSocket: end_call and mark_safe from the UI."""
import threading

import pytest
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


def test_mark_safe_releases_gate_and_lowers_risk(tmp_path):
    client, rt, hold = make(tmp_path, [ch("send the bank details", 0)])
    with client, client.websocket_connect("/ws") as ws:
        gate_state = next_of(ws, "gate")["data"]["state"]
        if gate_state != "locked":
            assert gate_state == "off"
            assert next_of(ws, "gate")["data"]["state"] == "locked"
        ws.send_json({"type": "mark_safe"})
        assert next_of(ws, "gate")["data"]["state"] == "off"
        assert next_of(ws, "check")["data"]["risk"] == "low"
        assert rt.pipeline.call_risk.risk == "low"
        hold.set()


@pytest.mark.parametrize("message", [{"type": "colleague"},
                                      {"type": "gate_release", "how": "colleague"}])
def test_colleague_button_releases_gate_and_posts_local_notification(tmp_path, monkeypatch, message):
    notifications = []
    monkeypatch.setattr("callguard.server.runtime.notify_colleague_macos", lambda: notifications.append(True))
    client, rt, hold = make(tmp_path, [ch("send the bank details", 0)])
    with client, client.websocket_connect("/ws") as ws:
        gate_state = next_of(ws, "gate")["data"]["state"]
        if gate_state != "locked":
            assert gate_state == "off"
            assert next_of(ws, "gate")["data"]["state"] == "locked"
        ws.send_json(message)
        assert next_of(ws, "gate")["data"]["state"] == "off"
        assert notifications == [True]
        assert rt.pipeline.call_risk.risk == "danger"
        assert rt.pipeline.call_risk.acted == ["colleague"]
        hold.set()


def test_reconnecting_ui_gets_call_state(tmp_path):
    client, rt, gate = make(tmp_path, [ch("do not tell anyone", 0)])
    with client:
        with client.websocket_connect("/ws") as ws:
            next_of(ws, "check")
        with client.websocket_connect("/ws") as ws2:
            assert ws2.receive_json()["type"] == "status"
            assert ws2.receive_json() == {"type": "rules", "data": [], "source": "default"}
            assert ws2.receive_json() == {"type": "call", "data": {"state": "started"}}
            assert ws2.receive_json()["data"]["risk"] == "danger"
        gate.set()


# ---------------------------------------------------------------- SRV-6 status
import asyncio
from pathlib import Path

from callguard.server import egress
from callguard.server.__main__ import build_app, parse_args

S1 = Path(__file__).parent / "fixtures" / "s1_government.txt"


def test_status_sent_first_on_connect(tmp_path, monkeypatch):
    monkeypatch.setenv("CALLGUARD_GATE", "off")
    hub = Hub()
    Runtime(hub, Pipeline(hub.broadcast, check_fn=lambda w, r: DANGER, rules=[]))
    with TestClient(create_app(hub, ui_dir=tmp_path)).websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "status", "data": {"listening": False, "online": False, "gate": "off"}}


def test_gate_mode_default_on(monkeypatch):
    monkeypatch.delenv("CALLGUARD_GATE", raising=False)
    assert Runtime.gate_mode() == "on"


def test_online_change_is_pushed(monkeypatch):
    sent = []

    async def go():
        hub = Hub()
        rt = Runtime(hub, Pipeline(hub.broadcast, check_fn=lambda w, r: DANGER, rules=[]))

        async def capture(t, d, **k):
            sent.append((t, d))
        hub.broadcast = capture
        monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
        await rt.refresh_online()
        await rt.refresh_online()  # no change, no message
        monkeypatch.setattr(egress, "_probe", lambda *a, **k: False)
        await rt.refresh_online()
        rt.close()
    asyncio.run(go())
    assert [d["online"] for t, d in sent if t == "status"] == [True, False]


def test_listening_true_during_fake_call():
    app, runtime = build_app(parse_args(["--fake", str(S1), "--fake-speed", "0"]))
    with TestClient(app) as client, client.websocket_connect("/ws") as ws:
        statuses = []
        while True:
            m = ws.receive_json()
            if m["type"] == "status":
                statuses.append(m["data"]["listening"])
            if m["type"] == "status" and statuses[-1] is False and len(statuses) > 1:
                break
    assert statuses[0] is False and True in statuses and statuses[-1] is False
