"""SRV-8: Tavily + Exa fallback, phone extraction, safe_org gate, once per org per call."""
import asyncio
import json
import threading
from pathlib import Path

import httpx
import pytest

from callguard.server import egress, fakes
from callguard.server.app import Hub
from callguard.server.pipeline import Pipeline
from callguard.server.runtime import Runtime
from callguard.server.verify import Verifier, wants_verify

S1 = Path(__file__).parent / "fixtures" / "s1_government.txt"
DOJ_PAGE = {"url": "https://www.justice.gov/contact-us", "title": "Contact the Department",
            "content": "Department of Justice main switchboard: (202) 514-2000."}


def lookup(org):
    return egress.search(org, [org])


@pytest.fixture
def net(monkeypatch):
    """Online with a fake transport; returns the list of requests that left."""
    sent = []

    def install(tavily=None, exa=None, tavily_key="t", exa_key=""):
        def handler(req: httpx.Request):
            sent.append((req.url.host, json.loads(req.content)))
            fn = tavily if req.url.host == egress.TAVILY_HOST else exa
            return fn(req) if fn else httpx.Response(500)
        monkeypatch.setattr(egress, "_probe", lambda *a, **k: True)
        monkeypatch.setattr(egress, "_transport", httpx.MockTransport(handler))
        monkeypatch.setenv("TAVILY_API_KEY", tavily_key)
        monkeypatch.setenv("EXA_API_KEY", exa_key)
        return sent
    return install


# ---------------------------------------------------------------- egress.search
def test_tavily_phone_and_source(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [
        {"url": "https://scamwatch.example.com", "content": "call 1-800-555-0199 now"}, DOJ_PAGE]}))
    v = lookup("Department of Justice")
    assert v == {"org": "Department of Justice", "status": "ok", "phone": "202-514-2000",
                 "source_url": "https://www.justice.gov/contact-us"}  # .gov preferred
    assert sent == [("api.tavily.com", {"query": "Department of Justice", "max_results": 5,
                                        "search_depth": "basic"})]


@pytest.mark.parametrize(("org", "phone", "url"), [
    ("Department of Justice", "202-514-2000", "https://www.justice.gov/contact-us"),
    ("Internal Revenue Service", "800-829-1040", "https://www.irs.gov/help"),
    ("Federal Trade Commission", "877-382-4357", "https://www.ftc.gov/contact"),
    ("Chase Bank", "800-935-9935", "https://www.chase.com/customer-service"),
    ("Microsoft Support", "800-642-7676", "https://support.microsoft.com/contactus"),
])
def test_five_org_result_shapes(net, org, phone, url):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [
        {"url": url, "content": f"Public line {phone}"}]}))
    assert lookup(org) == {"org": org, "status": "ok", "phone": phone, "source_url": url}
    assert sent[0][1]["query"] == org


def test_search_without_caller_lines_refuses_before_http(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    assert egress.search("Department of Justice")["status"] == "error"
    assert sent == [] and egress.entries[-1]["status"] == "refused"
    assert egress.entries[-1]["sent"] == ""


def test_search_enforces_env_never_search_before_http(net, monkeypatch):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    monkeypatch.setenv("CALLGUARD_NEVER_SEARCH", "Department of Justice")
    assert lookup("Department of Justice")["status"] == "error"
    assert sent == [] and egress.entries[-1]["status"] == "refused"


def test_no_phone_is_not_found_with_source(net):
    net(tavily=lambda r: httpx.Response(200, json={"results": [{"url": "https://irs.gov", "content": "no number"}]}))
    assert lookup("IRS") == {"org": "IRS", "status": "not_found", "source_url": "https://irs.gov"}


def test_exa_fallback_when_tavily_fails(net):
    sent = net(tavily=lambda r: httpx.Response(503),
               exa=lambda r: httpx.Response(200, json={"results": [
                   {"url": "https://www.ssa.gov", "title": "SSA", "text": "Call 800-772-1213"}]}),
               exa_key="e")
    v = lookup("Social Security Administration")
    assert v["status"] == "ok" and v["phone"] == "800-772-1213"
    assert [h for h, _ in sent] == ["api.tavily.com", "api.exa.ai"]
    assert sent[1][1]["query"] == "Social Security Administration"
    assert [(e["destination"], e["status"]) for e in egress.entries] == \
        [("api.tavily.com", "error"), ("api.exa.ai", "ok")]


def test_exa_fallback_when_tavily_has_no_phone(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [
        {"url": "https://www.justice.gov/about", "content": "About DOJ"}]}),
        exa=lambda r: httpx.Response(200, json={"results": [
            {"url": "https://www.justice.gov/contact-us", "text": "Call 202-514-2000"}]}),
        exa_key="e")
    assert lookup("Department of Justice")["status"] == "ok"
    assert [host for host, _ in sent] == [egress.TAVILY_HOST, egress.EXA_HOST]


def test_exa_works_when_tavily_probe_is_down(net, monkeypatch):
    sent = net(exa=lambda r: httpx.Response(200, json={"results": [
        {"url": "https://www.justice.gov/contact-us", "text": "Call 202-514-2000"}]}), exa_key="e")
    monkeypatch.setattr(egress, "_probe", lambda host=egress.TAVILY_HOST, **k: host == egress.EXA_HOST)
    assert lookup("Department of Justice")["status"] == "ok"
    assert [host for host, _ in sent] == [egress.EXA_HOST]


def test_bad_provider_json_never_raises(net):
    net(tavily=lambda r: httpx.Response(200, json=["unexpected response"]))
    assert lookup("Department of Justice")["status"] == "error"


def test_no_exa_key_means_tavily_only(net):
    sent = net(tavily=lambda r: httpx.Response(500))
    assert lookup("IRS")["status"] == "error"
    assert [h for h, _ in sent] == ["api.tavily.com"]


def test_exa_only_if_no_tavily_key(net):
    sent = net(exa=lambda r: httpx.Response(200, json={"results": []}), tavily_key="", exa_key="e")
    assert lookup("IRS")["status"] == "not_found"
    assert [h for h, _ in sent] == ["api.exa.ai"]


def test_offline_tries_nothing(net, monkeypatch):
    sent = net(tavily=lambda r: httpx.Response(200, json={}))
    monkeypatch.setattr(egress, "_probe", lambda *a, **k: False)
    assert lookup("IRS")["status"] == "offline" and sent == []


@pytest.mark.parametrize("text,phone", [
    ("Call (202) 514-2000.", "202-514-2000"), ("+1 800.772.1213", "800-772-1213"),
    ("case 4471-22 ref 12345678901234", ""), ("tel 202-514-2000x", ""),
])
def test_extract_phone(text, phone):
    assert egress.extract_phone([{"url": "https://a.gov", "text": text}])[0] == phone


# ---------------------------------------------------------------- Verifier
DOJ = {"risk": "watch", "tactics": ["authority", "threat"], "claimed_identity": "Department of Justice",
       "rules_broken": [], "reason": "", "next_step": "", "confidence": 0.71}


def test_wants_verify_threshold():
    assert wants_verify(DOJ)
    assert not wants_verify({**DOJ, "confidence": 0.31})
    assert not wants_verify({**DOJ, "claimed_identity": None})
    assert wants_verify({k: v for k, v in DOJ.items() if k != "confidence"})  # watch, no confidence
    assert not wants_verify({"risk": "low", "claimed_identity": "IRS"})


def run_verifier(lines, checks):
    msgs = []

    async def go():
        async def bc(t, d, **k):
            msgs.append((t, d))
        v = Verifier(bc, lambda: lines, lambda: 1)
        for c in checks:
            await v(c, c)
        await v.drain()
        return v
    v = asyncio.run(go())
    return msgs, v


def test_verifier_looks_up_once_per_org(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    msgs, _ = run_verifier(["I'm from the Department of Justice."], [DOJ, DOJ, {**DOJ, "risk": "danger", "confidence": 0.99}])
    assert len(sent) == 1
    assert msgs == [("verify", {"org": "Department of Justice"}),
                    ("verify", {"org": "Department of Justice", "status": "ok", "phone": "202-514-2000",
                                "source_url": "https://www.justice.gov/contact-us"})]


def test_verifier_refuses_unsafe_name_and_sends_nothing(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    msgs, _ = run_verifier(["Hello there."], [DOJ])  # caller never said it
    assert sent == []
    assert msgs == [("verify", {"org": "Department of Justice", "status": "error"})]
    assert egress.entries == [{**egress.entries[0], "sent": "", "status": "refused"}]


def test_verifier_honours_never_search(net, monkeypatch):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    monkeypatch.setenv("CALLGUARD_NEVER_SEARCH", "Department of Justice")
    run_verifier(["Department of Justice calling"], [DOJ])
    assert sent == [] and egress.entries[-1]["status"] == "refused"


def test_verifier_skips_low_confidence(net):
    sent = net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    msgs, _ = run_verifier(["Department of Justice calling"], [{**DOJ, "risk": "low", "confidence": 0.31}])
    assert sent == [] and msgs == [] and egress.entries == []


# ---------------------------------------------------------------- end to end
def test_s1_online_egress_log_is_exactly_one_entry(net):
    """Integration checklist: after S1 online, one entry, `Department of Justice`."""
    net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    hold = threading.Event()
    msgs = []

    async def go():
        hub = Hub()

        async def bc(t, d, **k):
            msgs.append((t, d))
        hub.broadcast = bc
        rt = Runtime(hub, Pipeline(bc, check_fn=fakes.fake_check, rules=[]))

        def stream():
            yield from fakes.fake_stream(S1, speed=0)
            hold.wait(5)  # keep the call open until the lookup is back

        task = asyncio.create_task(rt.pipeline.run(stream()))
        for _ in range(200):
            if any(t == "verify" and d.get("status") for t, d in msgs):
                break
            await asyncio.sleep(0.01)
        hold.set()
        await task
        await rt.verifier.drain()
        rt.close()
    asyncio.run(go())
    assert [(e["sent"], e["status"]) for e in egress.entries] == [("Department of Justice", "ok")]
    final = [d for t, d in msgs if t == "verify" and d.get("status")]
    assert final == [{"org": "Department of Justice", "status": "ok", "phone": "202-514-2000",
                      "source_url": "https://www.justice.gov/contact-us"}]


def test_instant_fake_replay_finishes_verify_before_call_end(net):
    net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))
    messages = []

    async def go():
        hub = Hub()

        async def capture(msg_type, data, **extra):
            messages.append((msg_type, data))

        hub.broadcast = capture
        rt = Runtime(hub, Pipeline(capture, check_fn=fakes.fake_check, rules=[]))
        await rt.pipeline.run_fake(S1, speed=0)
        rt.close()

    asyncio.run(go())
    assert any(t == "verify" and d.get("status") == "ok" for t, d in messages)
    assert max(i for i, (t, d) in enumerate(messages) if t == "verify" and d.get("status") == "ok") < \
        max(i for i, (t, d) in enumerate(messages) if t == "call" and d["state"] == "ended")


def test_call_end_clears_cache_so_next_call_looks_up_again(net):
    net(tavily=lambda r: httpx.Response(200, json={"results": [DOJ_PAGE]}))

    async def go():
        hub = Hub()
        rt = Runtime(hub, Pipeline(hub.broadcast, check_fn=lambda w, r: DOJ, rules=[]))
        rt.verifier.cache["department of justice"] = {"org": "x"}
        rt.pipeline.active = True
        await rt.pipeline.end_call()
        return rt.verifier.cache
    assert asyncio.run(go()) == {}
