import pytest

from callguard.server import egress


@pytest.fixture(autouse=True)
def temp_rules_file(monkeypatch, tmp_path):
    """Never read or write the real firm rules file (~/Library/...) from a test."""
    path = tmp_path / "custom_rules" / "rules.json"
    monkeypatch.setenv("CALLGUARD_RULES_FILE", str(path))
    return path


@pytest.fixture(autouse=True)
def clean_egress(monkeypatch):
    """Fresh egress state per test; the network is never reachable by default."""
    egress.entries.clear()
    egress._listeners.clear()
    monkeypatch.setattr(egress, "_online_cache", None)
    monkeypatch.setattr(egress, "_transport", None)
    monkeypatch.setattr(egress, "_probe", lambda *a, **k: False)
    monkeypatch.delenv("CALLGUARD_OFFLINE", raising=False)
    monkeypatch.delenv("TAVILY_API_KEY", raising=False)
    yield
    egress.entries.clear()
    egress._listeners.clear()
