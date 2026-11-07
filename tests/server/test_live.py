"""Live mode: callguard.audio.stream_chunks() wired into the pipeline and status."""
import asyncio
import queue
import threading

from callguard.server import runtime as runtime_mod
from callguard.server.__main__ import build_app, parse_args
from callguard.server.app import Hub
from callguard.server.pipeline import Pipeline
from callguard.server.runtime import Runtime

LOW = {"risk": "low", "tactics": [], "claimed_identity": None, "rules_broken": [],
       "reason": "", "next_step": "", "source": "model"}


def chunk(speaker, text, start):
    return {"speaker": speaker, "text": text, "start": start, "end": start + 3.0, "language": "en"}


class Sink:
    def __init__(self):
        self.msgs = []

    async def __call__(self, msg_type, data, **extra):
        self.msgs.append((msg_type, data))

    def calls(self):
        return [d["state"] for t, d in self.msgs if t == "call"]


def fed_stream(q):
    """A blocking generator, like the real audio stream, fed from a queue."""
    def make():
        while True:
            item = q.get()
            if item is None:
                return
            yield item
    return make


def test_live_call_ends_after_silence_and_next_speech_starts_a_new_call():
    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=lambda w, r: LOW, rules=[])
        q = queue.Queue()
        task = asyncio.create_task(p.run_live(fed_stream(q), idle_s=0.2))
        q.put(chunk("caller", "hello", 0))
        await asyncio.sleep(0.5)  # silence > idle_s
        assert sink.calls() == ["started", "ended"]
        assert not p.window  # cleared at call end
        q.put(chunk("caller", "hi again", 60))
        await asyncio.sleep(0.05)
        assert sink.calls() == ["started", "ended", "started"]
        q.put(None)  # stream stops (device lost / app quit)
        await asyncio.wait_for(task, 2)
        p.close()
        return sink
    sink = asyncio.run(go())
    assert sink.calls() == ["started", "ended", "started", "ended"]


def test_end_call_button_does_not_stop_live_audio():
    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=lambda w, r: LOW, rules=[])
        q = queue.Queue()
        task = asyncio.create_task(p.run_live(fed_stream(q), idle_s=30))
        q.put(chunk("caller", "one", 0))
        await asyncio.sleep(0.05)
        await p.end_call()  # UI "End call"
        q.put(chunk("caller", "two", 3))
        await asyncio.sleep(0.05)
        assert not task.done()
        assert sink.calls() == ["started", "ended", "started"]
        q.put(None)
        await asyncio.wait_for(task, 2)
        p.close()
    asyncio.run(go())


def test_audio_error_ends_stream_without_raising():
    def broken():
        raise RuntimeError("no BlackHole")
        yield  # pragma: no cover

    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=lambda w, r: LOW, rules=[])
        await asyncio.wait_for(p.run_live(broken), 2)
        p.close()
        return sink
    assert asyncio.run(go()).calls() == []


def test_runtime_reports_audio_health_and_retries():
    async def go():
        hub = Hub()
        sent = []

        async def bcast(t, d, **extra):
            sent.append((t, d))
        hub.broadcast = bcast
        hub.wait_for_client = lambda: asyncio.sleep(0)
        rt = Runtime(hub, Pipeline(bcast, check_fn=lambda w, r: LOW, rules=[]))
        answers = iter([(False, "No caller sound heard."), (True, "Audio inputs are ready.")])
        q = queue.Queue()
        task = asyncio.create_task(rt.run_live(fed_stream(q), health=lambda: next(answers), retry_s=0.05))
        await asyncio.sleep(0.2)
        statuses = [d for t, d in sent if t == "status"]
        assert statuses[0]["audio_ok"] is False and statuses[0]["audio_message"] == "No caller sound heard."
        assert statuses[-1]["audio_ok"] is True and statuses[-1]["listening"] is True
        task.cancel()
        rt.close()
    asyncio.run(go())


def test_status_says_model_degraded_on_fallback_checks():
    async def go():
        hub = Hub()
        sent = []

        async def bcast(t, d, **extra):
            sent.append((t, d))
        hub.broadcast = bcast
        rt = Runtime(hub, Pipeline(bcast, check_fn=lambda w, r: {**LOW, "source": "fallback"}, rules=[]))
        await rt.pipeline.feed(chunk("caller", "hello", 0))
        await rt.pipeline.drain()
        assert rt.status()["model"] == "degraded"
        rt.pipeline.check_fn = lambda w, r: LOW
        await rt.pipeline.feed(chunk("caller", "again", 3))
        await rt.pipeline.drain()
        assert rt.status()["model"] == "ok"
        assert [d.get("model") for t, d in sent if t == "status"] == ["degraded", "ok"]
        rt.close()
    asyncio.run(go())


def test_colleague_plus_gate_release_posts_one_heads_up(monkeypatch):
    posted = []
    monkeypatch.setattr(runtime_mod, "notify_colleague_macos", lambda: posted.append(1))

    async def go():
        hub = Hub()

        async def bcast(t, d, **extra):
            pass
        hub.broadcast = bcast
        rt = Runtime(hub, Pipeline(bcast, check_fn=lambda w, r: LOW, rules=[]))
        await rt.pipeline.feed(chunk("caller", "hello", 0))
        await rt._on_colleague({"type": "colleague"})
        await rt._on_gate_release({"type": "gate_release", "how": "colleague"})
        rt.close()
    asyncio.run(go())
    assert posted == [1]


def test_default_mode_listens_live_and_no_audio_skips_it():
    _, rt = build_app(parse_args([]))
    rt.close()
    assert parse_args([]).no_audio is False
    assert parse_args(["--no-audio"]).no_audio is True
