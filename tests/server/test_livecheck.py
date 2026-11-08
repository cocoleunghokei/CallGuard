"""SRV-8 live-check script, run against a fake Tavily (no network)."""
import json

import httpx
import pytest

from callguard.server import egress, livecheck


@pytest.fixture
def fake_tavily(monkeypatch):
    seen = []

    def handler(request):
        query = json.loads(request.content)["query"]
        seen.append(query)
        return httpx.Response(200, json={"results": [
            {"url": "https://www.example.gov/contact", "title": query, "content": "Call 202-514-2000"}]})

    monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
    monkeypatch.setattr(egress, "_online_cache", None)
    monkeypatch.setattr(egress, "_transport", httpx.MockTransport(handler))
    monkeypatch.setenv("TAVILY_API_KEY", "test-key")
    return seen


def test_all_orgs_found_sends_only_org_names(fake_tavily):
    lines = []
    assert livecheck.run(livecheck.ORGS, out=lines.append) == 0
    assert fake_tavily == livecheck.ORGS
    assert lines[-1] == "5/5 returned a phone number"
    assert sum("egress api.tavily.com" in l for l in lines) == 5


def test_missing_key_sends_nothing(fake_tavily, monkeypatch):
    monkeypatch.delenv("TAVILY_API_KEY")
    lines = []
    assert livecheck.run(livecheck.ORGS, out=lines.append) == 2
    assert fake_tavily == []
