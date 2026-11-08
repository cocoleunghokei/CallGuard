"""Emergency contacts: load / validate / save to one local file, and the WebSocket round trip."""
import json

import pytest
from fastapi.testclient import TestClient

from callguard.server import contacts
from callguard.server.app import Hub, create_app


@pytest.fixture(autouse=True)
def data_dir(tmp_path, monkeypatch):
    monkeypatch.setenv("CALLGUARD_DATA_DIR", str(tmp_path))
    return tmp_path


def test_defaults_when_no_file():
    got = contacts.load()
    assert [c["id"] for c in got] == ["oit", "manager"]
    assert got[0]["role"] == "IT security (OIT)" and got[1]["phone"] == ""


def test_broken_file_gives_defaults(data_dir):
    (data_dir / "contacts.json").write_text("{not json")
    assert contacts.load() == contacts.DEFAULTS


def test_save_and_load_round_trip(data_dir):
    cleaned, errors = contacts.validate([{"id": "manager", "name": "  Jane   Park ", "phone": "+1 (212) 555-0142 x12"}])
    assert errors == []
    contacts.save(cleaned)
    got = {c["id"]: c for c in contacts.load()}
    assert got["manager"]["name"] == "Jane Park" and got["manager"]["phone"] == "+1 (212) 555-0142 x12"
    assert got["oit"]["name"] == "OIT help desk", "untouched contact keeps its default"
    saved = json.loads((data_dir / "contacts.json").read_text())
    assert set(saved[0]) == {"id", "name", "phone"}, "roles are fixed, never stored"


def test_role_cannot_be_changed_and_unknown_ids_dropped():
    cleaned, errors = contacts.validate([
        {"id": "oit", "role": "Anything", "name": "Desk", "phone": "100"},
        {"id": "stranger", "name": "x", "phone": "1"},
    ])
    assert errors == []
    assert [c["id"] for c in cleaned] == ["oit", "manager"]
    assert cleaned[0]["role"] == "IT security (OIT)"


@pytest.mark.parametrize("bad", [
    {"id": "oit", "name": "x" * 61, "phone": ""},
    {"id": "oit", "name": "", "phone": "call me maybe"},
    {"id": "oit", "name": "", "phone": "1" * 31},
    {"id": "oit", "name": 5, "phone": ""},
])
def test_bad_input_refused(bad, data_dir):
    cleaned, errors = contacts.validate([bad])
    assert cleaned == [] and errors
    assert not (data_dir / "contacts.json").exists()


def test_not_a_list_refused():
    assert contacts.validate({"id": "oit"})[1]


def test_websocket_send_on_connect_and_save(tmp_path, data_dir):
    hub = Hub()
    contacts.attach(hub)
    with TestClient(create_app(hub, ui_dir=tmp_path)).websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first == {"type": "contacts", "data": contacts.DEFAULTS}
        ws.send_json({"type": "save_contacts", "data": [{"id": "manager", "name": "Jane", "phone": "555 0142"}]})
        msg = ws.receive_json()
        assert msg["type"] == "contacts" and msg["data"][1]["name"] == "Jane"
        assert ws.receive_json() == {"type": "contacts_saved", "data": {"ok": True}}
        ws.send_json({"type": "save_contacts", "data": [{"id": "manager", "name": "Jane", "phone": "not a number"}]})
        back = ws.receive_json()
        assert back["type"] == "contacts" and back["data"][1]["phone"] == "555 0142", "UI is put back to the saved list"
        bad = ws.receive_json()
        assert bad["type"] == "contacts_saved" and bad["data"]["ok"] is False and bad["data"]["errors"]
    assert contacts.load()[1]["phone"] == "555 0142", "a refused save leaves the file alone"


def test_build_app_sends_contacts_after_status_and_rules(tmp_path, monkeypatch):
    from callguard.server.__main__ import build_app, parse_args
    app, _rt = build_app(parse_args(["--no-audio"]))
    with TestClient(app).websocket_connect("/ws") as ws:
        types = [ws.receive_json()["type"] for _ in range(4)]
    assert types[:2] == ["status", "rules"] and "contacts" in types
