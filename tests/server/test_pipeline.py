"""SRV-2 / SRV-4: rolling window, skip-if-busy + one rerun, fake S1 replay."""
import asyncio
import logging
import threading
from pathlib import Path

from fastapi.testclient import TestClient

from callguard.server import fakes
from callguard.server.__main__ import build_app, parse_args
from callguard.server.pipeline import Pipeline, window_text

S1 = Path(__file__).parent / "fixtures" / "s1_government.txt"
LOW = {"risk": "low", "tactics": [], "claimed_identity": None, "rules_broken": [],
       "reason": "", "next_step": ""}


def chunk(speaker, text, start):
    return {"speaker": speaker, "text": text, "start": start, "end": start + 3.0, "language": "en"}


class Sink:
    def __init__(self):
        self.msgs = []

    async def __call__(self, msg_type, data, **extra):
        self.msgs.append((msg_type, data))

    def types(self):
        return [t for t, _ in self.msgs]


def run(coro):
    return asyncio.run(coro)


def test_window_keeps_last_30_seconds_with_speakers():
    async def go():
        p = Pipeline(Sink(), check_fn=lambda w, r: LOW, rules=[])
        for i in range(15):  # 45 s of call
            await p.feed(chunk("caller" if i % 2 else "you", f"line {i}", i * 3.0))
        await p.drain()
        return p
    p = run(go())
    assert [c["text"] for c in p.window] == [f"line {i}" for i in range(5, 15)]
    assert window_text(list(p.window)[:2]) == "caller: line 5\nyou: line 6"
    p.close()


def test_only_caller_chunks_trigger_checks():
    calls = []

    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=lambda w, r: calls.append(w) or LOW, rules=[])
        await p.feed(chunk("you", "hello", 0))
        await p.drain()
        await p.feed(chunk("caller", "hi there", 3))
        await p.drain()
        return sink
    sink = run(go())
    assert calls == ["you: hello\ncaller: hi there"]
    assert sink.types() == ["call", "transcript", "transcript", "check"]


def test_skip_if_busy_then_one_rerun_on_newest_window():
    started, release, windows = threading.Event(), threading.Event(), []

    def slow_check(w, r):
        windows.append(w)
        started.set()
        release.wait(5)
        return LOW

    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=slow_check, rules=[])
        await p.feed(chunk("caller", "one", 0))
        await asyncio.to_thread(started.wait, 5)
        for i, t in enumerate(["two", "three", "four"], 1):
            await p.feed(chunk("caller", t, i * 3.0))
        release.set()
        await p.drain()
        return sink
    sink = run(go())
    assert len(windows) == 2  # first + exactly one rerun
    assert windows[1].endswith("caller: four")
    assert sink.types().count("check") == 2


def test_check_exception_is_swallowed_and_logged_without_text(caplog):
    def boom(w, r):
        raise RuntimeError("secret transcript words")

    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=boom, rules=[])
        await p.feed(chunk("caller", "my account is 1234", 0))
        await p.drain()
        return sink
    with caplog.at_level(logging.DEBUG):
        sink = run(go())
    assert sink.types() == ["call", "transcript"]
    assert "1234" not in caplog.text and "secret" not in caplog.text


def test_fake_s1_replay_pushes_expected_sequence():
    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=fakes.fake_check, rules=[])
        await p.run_fake(S1, speed=0)
        p.close()
        return sink
    sink = run(go())
    risks = [d["risk"] for t, d in sink.msgs if t == "check"]
    assert sink.types().count("transcript") == 5
    assert risks[0] == "low" and risks[-1] == "danger" and "watch" in risks
    first = next(d for t, d in sink.msgs if t == "check")
    assert first["claimed_identity"] == "Department of Justice"


def test_fake_stream_matches_contract():
    chunks = list(fakes.fake_stream(S1, speed=0))
    assert [c["speaker"] for c in chunks] == ["caller", "caller", "you", "caller", "caller"]
    assert chunks[1] == {"speaker": "caller", "text": chunks[1]["text"], "start": 3.0, "end": 6.0, "language": "en"}


def test_cli_fake_flags(tmp_path):
    args = parse_args(["--fake", str(S1), "--fake-speed", "4"])
    assert args.fake == str(S1) and args.fake_speed == 4.0


def test_fake_call_over_websocket(tmp_path):
    app, runtime = build_app(parse_args(["--fake", str(S1), "--fake-speed", "0"]))
    client = TestClient(app)
    with client, client.websocket_connect("/ws") as ws:
        got = [m for m in (ws.receive_json() for _ in range(10))
               if m["type"] in ("call", "transcript", "check")][:6]
    assert got.pop(0) == {"type": "call", "data": {"state": "started"}}
    assert got[0] == {"type": "transcript", "data": {"speaker": "caller", "start": 0.0, "end": 3.0,
                      "language": "en", "text": "Hi, this is Officer Chen from the Department of Justice."}}
    assert {m["type"] for m in got} <= {"transcript", "check", "call"}


# ---------------------------------------------------------------- SRV-5 lifecycle
def test_fake_call_starts_and_ends_and_forgets():
    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=fakes.fake_check, rules=[])
        ended = []
        p.on_call_end.append(lambda: ended.append(True))
        await p.run_fake(S1, speed=0)
        return sink, p, ended
    sink, p, ended = run(go())
    assert sink.msgs[0] == ("call", {"state": "started"})
    assert sink.msgs[-1] == ("call", {"state": "ended"})
    assert ended == [True]
    assert len(p.window) == 0 and p.call_risk.shown is None and not p.active
    p.close()


def test_end_call_from_ui_stops_replay_and_drops_inflight_check():
    started, release = threading.Event(), threading.Event()

    def slow(w, r):
        started.set()
        release.wait(5)
        return {**LOW, "risk": "danger"}

    def stream():
        yield chunk("caller", "one", 0)
        yield chunk("caller", "two", 3)
        yield chunk("caller", "three", 6)

    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=slow, rules=[])
        task = asyncio.create_task(p.run(stream()))
        await asyncio.to_thread(started.wait, 5)
        await p.end_call()  # UI pressed "end call" mid-check
        release.set()
        await task
        await p.drain()
        return sink, p
    sink, p = run(go())
    assert "check" not in sink.types()  # stale result for the ended call dropped
    assert sink.types().count("call") == 2 and sink.msgs[-1] == ("call", {"state": "ended"})
    assert len(p.window) == 0
    p.close()


def test_live_stream_starts_a_new_call_after_end():
    async def go():
        sink = Sink()
        p = Pipeline(sink, check_fn=lambda w, r: LOW, rules=[])
        await p.feed(chunk("caller", "a", 0))
        await p.drain()
        await p.end_call()
        await p.feed(chunk("caller", "b", 0))
        await p.drain()
        return sink, p
    sink, p = run(go())
    assert [d["state"] for t, d in sink.msgs if t == "call"] == ["started", "ended", "started"]
    assert [c["text"] for c in p.window] == ["b"]
    p.close()
