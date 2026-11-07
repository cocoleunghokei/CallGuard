"""SRV-9: soft gate transitions, timeout, release paths, and call lifecycle."""
import asyncio
from pathlib import Path

from callguard.server import fakes
from callguard.server.app import Hub
from callguard.server.gate import LOCK_CONFIDENCE, SoftGate
from callguard.server.pipeline import Pipeline
from callguard.server.runtime import Runtime


def check(*tactics, confidence=0.99, risk="danger"):
    return {"risk": risk, "tactics": list(tactics), "claimed_identity": None,
            "rules_broken": [], "reason": "call content must not enter gate", "next_step": "",
            "confidence": confidence}


def run(coro):
    return asyncio.run(coro)


def test_off_arms_on_danger_then_locks_on_eligible_ask():
    async def go():
        sent = []

        async def push(t, d):
            sent.append((t, d))

        gate = SoftGate(push)
        await gate.on_check(check(risk="watch"), check(risk="watch"))
        assert gate.snapshot()["state"] == "off"
        await gate.on_check(check("secrecy"), check("secrecy"))
        assert gate.snapshot()["state"] == "armed"
        await gate.on_check(check("bank_change", confidence=LOCK_CONFIDENCE - 0.01), check("bank_change"))
        assert gate.snapshot()["state"] == "armed"
        await gate.on_check(check("bank_change", confidence=LOCK_CONFIDENCE), check("bank_change"))
        assert gate.snapshot()["state"] == "locked"
        assert gate.snapshot()["release_in"] == 120
        assert [data["state"] for _, data in sent] == ["armed", "locked"]
        assert all("call content" not in str(data) for _, data in sent)
        await gate.reset()

    run(go())


def test_off_locks_directly_and_off_switch_blocks_it(monkeypatch):
    async def go():
        sent = []

        async def push(t, d):
            sent.append(d)

        monkeypatch.setenv("CALLGUARD_GATE", "off")
        gate = SoftGate(push)
        await gate.on_check(check("bank_change"), check("bank_change"))
        assert gate.snapshot()["state"] == "off" and sent == []
        monkeypatch.setenv("CALLGUARD_GATE", "on")
        await gate.on_check(check("bank_change"), check("bank_change"))
        assert [d["state"] for d in sent] == ["locked"]
        monkeypatch.setenv("CALLGUARD_GATE", "off")
        await gate.on_check(check("bank_change"), check("bank_change"))
        assert [d["state"] for d in sent] == ["locked", "off"]

    run(go())


def test_release_no_renag_until_new_ask_and_reset_for_next_call():
    async def go():
        sent = []

        async def push(t, d):
            sent.append(d["state"])

        gate = SoftGate(push)
        first = check("bank_change")
        await gate.on_check(first, first)
        assert not await gate.release("invalid")
        assert await gate.release("hang_up")
        assert gate.snapshot()["state"] == "off" and gate.state == "released"
        await gate.on_check(first, first)
        assert gate.state == "released"
        second = check("bank_change", "credential_request")
        await gate.on_check(second, second)
        assert gate.state == "locked"
        assert await gate.release("colleague")
        await gate.on_check(second, second)
        assert gate.state == "released"
        await gate.reset()
        assert gate.seen_asks == set() and gate.state == "off"
        await gate.on_check(first, first)
        assert gate.state == "locked"
        assert sent == ["locked", "off", "locked", "off", "locked"]
        await gate.reset()

    run(go())


def test_mark_safe_from_armed_and_call_end_from_locked():
    async def go():
        sent = []

        async def push(t, d):
            sent.append(d["state"])

        gate = SoftGate(push)
        await gate.on_check(check("secrecy"), check("secrecy"))
        assert await gate.release("mark_safe")
        assert gate.state == "released"
        await gate.reset()
        await gate.on_check(check("bank_change"), check("bank_change"))
        await gate.reset()
        assert gate.state == "off" and gate.deadline is None
        assert sent == ["armed", "off", "locked", "off"]

    run(go())


def test_timeout_auto_releases_and_old_ask_stays_released():
    async def go():
        sent = []

        async def push(t, d):
            sent.append(d["state"])

        gate = SoftGate(push, timeout=0.02)
        ask = check("bank_change")
        await gate.on_check(ask, ask)
        await asyncio.sleep(0.04)
        assert gate.state == "released" and gate.snapshot()["release_in"] == 0
        await gate.on_check(ask, ask)
        assert sent == ["locked", "off"]

    run(go())


def test_gate_release_ui_message_marks_safe_and_end_clears_gate():
    async def go():
        sent = []
        hub = Hub()

        async def push(t, d, **extra):
            sent.append((t, d))

        hub.broadcast = push
        rt = Runtime(hub, Pipeline(push, check_fn=lambda w, r: check("bank_change"), rules=[]))
        await rt.pipeline.feed({"speaker": "caller", "text": "send bank details", "start": 0,
                                "end": 3, "language": "en"})
        await rt.pipeline.drain()
        assert rt.gate.state == "locked"
        await hub.dispatch({"type": "gate_release", "how": "mark_safe"})
        assert rt.gate.state == "released" and rt.pipeline.call_risk.risk == "low"
        assert ("gate", {"state": "off", "reason": "", "release_in": 0}) in sent
        await rt.pipeline.end_call()
        assert rt.gate.state == "off" and rt.gate.seen_asks == set()
        rt.close()

    run(go())


def test_fake_s1_replay_locks_then_clears_gate():
    script = Path(__file__).parent / "fixtures" / "s1_government.txt"
    messages = []

    async def go():
        hub = Hub()

        async def push(t, d, **extra):
            messages.append((t, d))

        hub.broadcast = push
        rt = Runtime(hub, Pipeline(push, check_fn=fakes.fake_check, rules=[]))
        await rt.pipeline.run_fake(script, speed=0)
        rt.close()

    run(go())
    states = [data["state"] for kind, data in messages if kind == "gate"]
    assert "locked" in states and states[-1] == "off"
    assert max(i for i, (kind, data) in enumerate(messages) if kind == "gate" and data["state"] == "locked") < \
        max(i for i, (kind, data) in enumerate(messages) if kind == "call" and data["state"] == "ended")
