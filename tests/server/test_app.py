"""SRV-1: static UI (or placeholder), /ws broadcast and client dispatch."""
import pytest
from fastapi.testclient import TestClient

from callguard.server.__main__ import parse_args
from callguard.server.app import Hub, create_app


def test_placeholder_when_ui_missing(tmp_path):
    client = TestClient(create_app(ui_dir=tmp_path))
    r = client.get("/")
    assert r.status_code == 200
    assert "Callguard" in r.text


def test_serves_ui_index(tmp_path):
    (tmp_path / "index.html").write_text("<h1>real ui</h1>")
    client = TestClient(create_app(ui_dir=tmp_path))
    r = client.get("/")
    assert r.status_code == 200
    assert "real ui" in r.text


def test_broadcast_reaches_all_clients(tmp_path):
    hub = Hub()
    client = TestClient(create_app(hub, ui_dir=tmp_path))
    received = []

    async def on_mark_safe(msg):
        await hub.broadcast("call", {"state": "ended"})

    hub.handle("mark_safe", on_mark_safe)
    with client.websocket_connect("/ws") as a, client.websocket_connect("/ws") as b:
        a.send_json({"type": "mark_safe"})
        received.append(a.receive_json())
        received.append(b.receive_json())
    assert received == [{"type": "call", "data": {"state": "ended"}}] * 2


def test_client_messages_dispatched_and_bad_ones_ignored(tmp_path):
    hub = Hub()
    got = []
    hub.handle("gate_release", lambda m: got.append(m))
    hub.handle("end_call", lambda m: got.append(m))
    client = TestClient(create_app(hub, ui_dir=tmp_path))
    with client.websocket_connect("/ws") as ws:
        ws.send_text("not json")
        ws.send_json({"type": "nope"})
        ws.send_json(["list"])
        ws.send_json({"type": "colleague"})  # valid, no handler yet
        ws.send_json({"type": "gate_release", "how": "hang_up"})
        ws.send_json({"type": "end_call"})
    assert got == [{"type": "gate_release", "how": "hang_up"}, {"type": "end_call"}]


def test_on_connect_hook_sends_first(tmp_path):
    hub = Hub()

    async def hello(ws):
        await hub.send(ws, "status", {"listening": False, "online": False})

    hub.on_connect.append(hello)
    client = TestClient(create_app(hub, ui_dir=tmp_path))
    with client.websocket_connect("/ws") as ws:
        assert ws.receive_json() == {"type": "status", "data": {"listening": False, "online": False}}


def test_rejects_unknown_types():
    hub = Hub()
    with pytest.raises(ValueError):
        hub.message("secret", {})
    with pytest.raises(ValueError):
        hub.handle("whatever", lambda m: None)


def test_rules_message_carries_top_level_source():
    assert Hub.message("rules", [], source="default") == {"type": "rules", "data": [], "source": "default"}


def test_cli_flags():
    assert parse_args(["--browser"]).browser is True
    assert parse_args([]).port == 8000
