"""SRV-3: egress log, offline handling, fake transport, localhost-only Ollama."""
import httpx
import pytest
from fastapi.testclient import TestClient

from callguard.server import egress
from callguard.server.app import Hub, create_app


@pytest.fixture
def online_with(monkeypatch):
    """Pretend we are online, with a fake transport handling every request."""
    def install(handler):
        monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
        monkeypatch.setattr(egress, "_transport", httpx.MockTransport(handler))
        monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    return install


def test_offline_returns_status_and_logs_entry():
    pushed = []
    egress.subscribe(pushed.append)
    verify = egress.search("Department of Justice")
    assert verify == {"org": "Department of Justice", "status": "offline"}
    assert pushed == egress.entries
    assert pushed[0]["destination"] == "api.tavily.com"
    assert pushed[0]["sent"] == "Department of Justice"
    assert pushed[0]["status"] == "offline"


def test_forced_offline_env(monkeypatch):
    monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
    monkeypatch.setenv("CALLGUARD_OFFLINE", "1")
    assert egress.online() is False


def test_ok_search_sends_only_the_query(online_with):
    seen = []

    def handler(request: httpx.Request):
        seen.append(request)
        return httpx.Response(200, json={"results": [{"url": "https://www.justice.gov", "content": "202-514-2000"}]})

    online_with(handler)
    verify = egress.search("Department of Justice")
    assert verify == {"org": "Department of Justice", "status": "ok", "phone": "202-514-2000",
                      "source_url": "https://www.justice.gov"}
    assert len(seen) == 1 and seen[0].url.host == "api.tavily.com"
    import json
    assert json.loads(seen[0].content) == {"query": "Department of Justice", "max_results": 5, "search_depth": "basic"}
    assert egress.entries == [{"time": egress.entries[0]["time"], "destination": "api.tavily.com",
                               "sent": "Department of Justice", "status": "ok"}]


def test_entry_recorded_before_request_leaves(online_with):
    at_send = []

    def handler(request):
        at_send.append([dict(e) for e in egress.entries])
        return httpx.Response(200, json={"results": []})

    online_with(handler)
    verify = egress.search("IRS")
    assert at_send[0][0]["sent"] == "IRS"
    assert verify["status"] == "not_found"


def test_connect_error_is_offline_and_never_raises(online_with):
    def handler(request):
        raise httpx.ConnectError("no route")

    online_with(handler)
    verify = egress.search("IRS")
    assert verify["status"] == "offline"
    assert egress.entries[-1]["status"] == "offline"


def test_server_error_is_error(online_with):
    online_with(lambda r: httpx.Response(500))
    verify = egress.search("IRS")
    assert verify["status"] == "error"
    assert egress.entries[-1]["status"] == "error"


def test_missing_key_sends_nothing(online_with, monkeypatch):
    seen = []
    online_with(lambda r: seen.append(r) or httpx.Response(200, json={}))
    monkeypatch.delenv("TAVILY_API_KEY")
    verify = egress.search("IRS")
    assert verify["status"] == "error" and seen == []
    assert egress.entries[-1]["sent"] == ""


@pytest.mark.parametrize("bad", ["x" * 81, "Department\nof Justice", "", "   ", None, 42])
def test_search_refuses_long_or_multiline_input(bad, online_with):
    seen = []
    online_with(lambda r: seen.append(r) or httpx.Response(200, json={}))
    egress.search(bad)
    assert seen == []
    assert egress.entries[-1] == {**egress.entries[-1], "sent": "", "status": "refused"}


def test_online_probe_is_cached(monkeypatch):
    calls = []
    monkeypatch.setattr(egress, "_probe", lambda *a, **k: calls.append(1) or True)
    assert egress.online() and egress.online()
    assert len(calls) == 1
    assert egress.online(force=True) and len(calls) == 2
    assert egress.entries == []  # the probe is not egress


def test_local_ollama_post_only_localhost(monkeypatch):
    monkeypatch.setattr(egress, "_transport", httpx.MockTransport(
        lambda r: httpx.Response(200, json={"message": {"content": "{}"}})))
    assert egress.local_ollama_post("http://localhost:11434/api/chat", {"x": 1}) == {"message": {"content": "{}"}}
    assert egress.local_ollama_post("http://127.0.0.1:11434/api/chat", {}) == {"message": {"content": "{}"}}
    for url in ["http://api.openai.com/v1/chat", "https://localhost:11434/api/chat",
                "http://localhost.evil.com/api", "http://10.0.0.5:11434/api/chat"]:
        with pytest.raises(ValueError):
            egress.local_ollama_post(url, {})
    assert egress.entries == []


def test_local_ollama_down_raises_local_model_error(monkeypatch):
    def handler(r):
        raise httpx.ConnectError("refused")
    monkeypatch.setattr(egress, "_transport", httpx.MockTransport(handler))
    with pytest.raises(egress.LocalModelError):
        egress.local_ollama_post("http://localhost:11434/api/chat", {})


def test_egress_entries_reach_the_websocket(tmp_path):
    hub = Hub()
    client = TestClient(create_app(hub, ui_dir=tmp_path))
    egress.search("Department of Justice")  # offline entry before connect
    with client.websocket_connect("/ws") as ws:
        first = ws.receive_json()
        assert first["type"] == "egress" and first["data"]["status"] == "offline"
        hub.handle("colleague", lambda m: egress.search("IRS"))
        ws.send_json({"type": "colleague"})
        live = ws.receive_json()
        assert live["type"] == "egress" and live["data"]["sent"] == "IRS"
