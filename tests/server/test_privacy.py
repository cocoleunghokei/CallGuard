"""SRV-12: privacy guarantees (prd §11). These are the product, not nice-to-haves."""
import ast
import asyncio
import builtins
import io
import os
from pathlib import Path

import httpx
import pytest

from callguard.server import egress, fakes
from callguard.server.pipeline import Pipeline

REPO = Path(__file__).resolve().parents[2]
S1 = Path(__file__).parent / "fixtures" / "s1_government.txt"

# (a) network + cloud-LLM modules nobody but egress.py may import
BANNED = {"requests", "httpx", "urllib", "urllib3", "socket", "http.client", "aiohttp",
          "tavily", "exa_py", "openai", "anthropic"}


def _imports(tree):
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                yield a.name
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            yield node.module
            for a in node.names:  # "from http import client"
                yield f"{node.module}.{a.name}"
        elif isinstance(node, ast.Call) and getattr(node.func, "id", None) == "__import__":
            if node.args and isinstance(node.args[0], ast.Constant):
                yield str(node.args[0].value)


def _banned(name):
    return any(name == b or name.startswith(b + ".") for b in BANNED)


def test_a_only_egress_imports_network_modules():
    offenders = []
    files = sorted((REPO / "callguard").rglob("*.py"))
    assert files, "scan found no files"
    for path in files:
        if path == REPO / "callguard" / "server" / "egress.py":
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        offenders += [f"{path.relative_to(REPO)}: {m}" for m in _imports(tree) if _banned(m)]
    assert offenders == []


def test_a_scanner_catches_offenders():
    src = "import requests\nfrom http import client\nfrom urllib.request import urlopen\nimport socket as s\n"
    found = [m for m in _imports(ast.parse(src)) if _banned(m)]
    assert {"requests", "http.client", "urllib.request", "socket"} <= set(found)
    assert not [m for m in _imports(ast.parse("from http import HTTPStatus")) if _banned(m)]


# (b) a whole fake call writes nothing to disk
def test_b_fake_s1_call_writes_nothing(monkeypatch):
    writes = []
    real_open, real_os_open, real_write = builtins.open, os.open, os.write

    def guarded_open(file, mode="r", *a, **k):
        if any(c in mode for c in "wax+"):
            writes.append(("open", str(file), mode))
        return real_open(file, mode, *a, **k)

    def guarded_os_open(path, flags, *a, **k):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_APPEND):
            writes.append(("os.open", str(path), flags))
        return real_os_open(path, flags, *a, **k)

    def guarded_write(fd, data):
        writes.append(("os.write", fd, len(data)))
        return real_write(fd, data)

    monkeypatch.setattr(builtins, "open", guarded_open)
    monkeypatch.setattr(io, "open", guarded_open)
    monkeypatch.setattr(os, "open", guarded_os_open)
    monkeypatch.setattr(os, "write", guarded_write)

    sent = []

    async def sink(msg_type, data, **extra):
        sent.append(msg_type)
        if msg_type == "check" and data.get("claimed_identity"):
            egress.search(data["claimed_identity"], [data["claimed_identity"]])  # offline in tests

    async def call():
        p = Pipeline(sink, check_fn=fakes.fake_check, rules=[])
        await p.run_fake(S1, speed=0)
        p.close()

    asyncio.run(call())
    assert "check" in sent and egress.entries  # the call really ran
    assert writes == []


# (c) search() input limits
@pytest.mark.parametrize("bad", ["D" * 81, "Department of\nJustice", "IRS\r"])
def test_c_search_refuses_long_or_multiline(bad, monkeypatch):
    seen = []
    monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
    monkeypatch.setattr(egress, "_transport", httpx.MockTransport(lambda r: seen.append(r) or httpx.Response(200, json={})))
    monkeypatch.setenv("TAVILY_API_KEY", "k")
    egress.search(bad, [bad])
    assert seen == []
    assert egress.entries[-1]["status"] == "refused" and egress.entries[-1]["sent"] == ""


# (d) safe_org()
CALLER = [
    "Hi, this is Agent John Miller, DOJ.",
    "I'm calling from the Department of Justice about DOJ case 4471-22.",
    "This is Chase, acct ending 8812, fraud team.",
    "Acme Legal Partners asked us to call.",
]
YOU = ["I work at Hartwell Capital, can I call you back?"]
NEVER = ["Acme Legal Partners"]


@pytest.mark.parametrize("org", [
    "Agent John Miller, DOJ",
    "DOJ case 4471-22",
    "Chase, acct ending 8812",
    "Acme Legal Partners",          # on the never-search list
    "Federal Trade Commission",     # caller never said it
    "Hartwell Capital",             # only the user said it
    "John Miller",                  # a person
    "justice.gov",
    "Department of Justice Office of the Inspector General Fraud Unit",  # > 6 words
])
def test_d_safe_org_refuses(org):
    assert egress.safe_org(org, CALLER, NEVER) is False
    assert org not in egress.org_refusal(org, CALLER, NEVER)  # reasons never echo the name


def test_d_safe_org_accepts_department_of_justice():
    assert egress.safe_org("Department of Justice", CALLER, NEVER) is True
    assert egress.safe_org("department of  justice", CALLER, NEVER) is True
    assert egress.safe_org("DOJ", CALLER, NEVER) is True


def test_d_never_search_from_env(monkeypatch):
    monkeypatch.setenv("CALLGUARD_NEVER_SEARCH", " Acme LLP , ,Client Co")
    assert egress.never_search_from_env() == ["Acme LLP", "Client Co"]
    monkeypatch.delenv("CALLGUARD_NEVER_SEARCH")
    assert egress.never_search_from_env() == []
