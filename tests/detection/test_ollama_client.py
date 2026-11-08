"""DET-2: the Ollama client builds the right request and fails cleanly. Fake transport only."""
import ast
import sys
import types
from pathlib import Path

import pytest

from callguard.detection import ollama_client as oc

WINDOW = "caller: Hi, this is Jake from IT.\nyou: Oh, hi."


class FakePost:
    def __init__(self, reply=None, exc=None):
        self.reply = reply if reply is not None else {"message": {"content": '{"tactics": []}'}}
        self.exc = exc
        self.calls = []

    def __call__(self, url, payload, timeout=None):
        self.calls.append((url, payload, timeout))
        if self.exc:
            raise self.exc
        return self.reply


def test_request_shape():
    post = FakePost()
    assert oc.chat(WINDOW, post=post) == '{"tactics": []}'
    url, payload, timeout = post.calls[0]
    assert url == "http://localhost:11434/api/chat"
    assert timeout == oc.TIMEOUT_S
    assert payload["format"] == "json"
    assert payload["stream"] is False
    assert payload["options"]["temperature"] == 0
    assert payload["options"]["num_ctx"] >= 2048
    system, user = payload["messages"]
    assert system["role"] == "system" and system["content"] == oc.system_prompt()
    assert user["role"] == "user" and user["content"].endswith(WINDOW)


def test_model_from_env(monkeypatch):
    monkeypatch.delenv("CALLGUARD_MODEL", raising=False)
    assert oc.build_payload(WINDOW)["model"] == "qwen2.5:7b"
    monkeypatch.setenv("CALLGUARD_MODEL", "qwen2.5:3b")
    assert oc.build_payload(WINDOW)["model"] == "qwen2.5:3b"
    assert oc.build_payload(WINDOW, model="other")["model"] == "other"


@pytest.mark.parametrize("exc", [TimeoutError(), ConnectionError(), ValueError("x"), RuntimeError()])
def test_transport_errors_become_ollama_error(exc):
    with pytest.raises(oc.OllamaError):
        oc.chat(WINDOW, post=FakePost(exc=exc))


@pytest.mark.parametrize("reply", [{}, {"message": None}, {"message": {}}, {"message": {"content": ""}},
                                   {"message": {"content": 5}}, [], "nope"])
def test_bad_replies_become_ollama_error(reply):
    with pytest.raises(oc.OllamaError):
        oc.chat(WINDOW, post=FakePost(reply=reply))


def test_errors_never_carry_transcript_text():
    secret = "my account number is 12345678"
    with pytest.raises(oc.OllamaError) as e:
        oc.chat("caller: " + secret, post=FakePost(exc=ValueError(secret)))
    assert secret not in str(e.value)


def test_default_transport_is_egress_local_ollama_post(monkeypatch):
    post = FakePost()
    fake = types.ModuleType("callguard.server.egress")
    fake.local_ollama_post = post
    monkeypatch.setitem(sys.modules, "callguard.server.egress", fake)
    oc.chat(WINDOW)
    assert post.calls


def test_missing_egress_is_an_ollama_error(monkeypatch):
    monkeypatch.setitem(sys.modules, "callguard.server.egress", None)
    with pytest.raises(oc.OllamaError):
        oc.chat(WINDOW)


def test_detection_lane_imports_no_network_library():
    banned = {"requests", "httpx", "urllib", "urllib3", "aiohttp", "socket", "http", "tavily", "exa_py"}
    for path in (Path(__file__).parents[2] / "callguard" / "detection").glob("*.py"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            names = []
            if isinstance(node, ast.Import):
                names = [a.name for a in node.names]
            elif isinstance(node, ast.ImportFrom) and node.module:
                names = [node.module]
            for n in names:
                assert n.split(".")[0] not in banned, f"{path.name} imports {n}"


def test_timeout_leaves_room_for_the_longest_window():
    # Live eval: S1's last beat took ~8 s on the demo Mac and timed out at 8.0 s.
    assert oc.TIMEOUT_S >= 12
