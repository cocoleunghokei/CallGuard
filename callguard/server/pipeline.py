"""SRV-2: transcript chunks in, `transcript` and `check` messages out.

Keeps a speaker-labelled rolling 30 s window in memory only. Each caller chunk
asks for a check() in a single worker thread; if one is already running we
skip, and run exactly once more when it finishes (on the newest window).
Logs latency and sizes, never transcript text.
"""
from __future__ import annotations

import asyncio
import logging
import os
import threading
import time
from collections import deque
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Any, Callable, Iterable, Iterator

from callguard.server.callrisk import CallRisk
from callguard.shared.contracts import Rule, ScamCheck, TranscriptChunk

log = logging.getLogger("callguard.server.pipeline")

WINDOW_SECONDS = 30.0
# Live audio has no "end of script": a call ends after this much silence (or End call).
CALL_IDLE_S = float(os.environ.get("CALLGUARD_CALL_IDLE_S", "45"))
CheckFn = Callable[[str, list[Rule]], ScamCheck]


def load_check() -> CheckFn:
    try:
        from callguard.detection import check  # type: ignore[attr-defined]
        return check
    except ImportError:
        from callguard.server.fakes import fake_check
        log.warning("callguard.detection.check missing, using server fake_check")
        return fake_check


def load_rules() -> list[Rule]:
    return load_rules_with_source()[0]


def load_rules_with_source() -> tuple[list[Rule], str]:
    """The firm's custom rules if saved and valid, else the defaults (prd §8.1)."""
    try:
        from callguard.detection.rules import load_rules_with_source as _load  # type: ignore[import-not-found]
        return _load()
    except Exception:
        return [], "default"


def load_fake_stream() -> Callable[..., Iterator[TranscriptChunk]]:
    try:
        from callguard.audio import fake_stream  # type: ignore[attr-defined]
        return fake_stream
    except ImportError:
        from callguard.server.fakes import fake_stream
        log.warning("callguard.audio.fake_stream missing, using server fake_stream")
        return fake_stream


def window_text(chunks: Iterable[TranscriptChunk]) -> str:
    """Speaker-labelled lines, oldest first: 'caller: …' / 'you: …'."""
    return "\n".join(f"{c['speaker']}: {c['text']}" for c in chunks)


class Pipeline:
    def __init__(self, broadcast: Callable[..., Any], check_fn: CheckFn | None = None,
                 rules: list[Rule] | None = None, window_seconds: float = WINDOW_SECONDS) -> None:
        self.broadcast = broadcast  # async (type, data) -> None
        self.check_fn = check_fn or load_check()
        if rules is not None:
            self.rules, self.rules_source = rules, "default"
        else:
            self.rules, self.rules_source = load_rules_with_source()
        self.window_seconds = window_seconds
        self.window: deque[TranscriptChunk] = deque()
        self._executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="detect")
        self._task: asyncio.Task | None = None
        self._pending = False
        self.call_risk = CallRisk()
        # Called with (raw window check, smoothed call check): gate, verify.
        self.on_check: list[Callable[[ScamCheck, ScamCheck], Any]] = []
        self.on_stream_end: list[Callable[[], Any]] = []  # finish async verify before a replay clears the call
        self.on_call_end: list[Callable[[], Any]] = []  # verify cache, gate, ...
        self.call_id = 0
        self.active = False
        self._stop = False

    # ------------------------------------------------------------ window
    def _prune(self) -> None:
        if not self.window:
            return
        newest = self.window[-1]["end"]
        while self.window and self.window[0]["end"] <= newest - self.window_seconds:
            self.window.popleft()

    def caller_lines(self) -> list[str]:
        return [c["text"] for c in self.window if c["speaker"] == "caller"]

    def clear(self) -> None:
        self.window.clear()
        self._pending = False
        self.call_risk.reset()

    # ------------------------------------------------------------ call lifecycle (SRV-5)
    async def start_call(self) -> None:
        self.clear()
        self.call_id += 1
        self.active = True
        await self.broadcast("call", {"state": "started"})

    async def end_call(self) -> None:
        """Call over (stream ended, or `end_call` from the UI): forget everything."""
        if not self.active:
            return
        self.active = False
        self._stop = True  # a replay stops; live audio starts a new call on its next chunk
        self.call_id += 1  # any check still running belongs to the old call: dropped
        self.clear()
        for fn in self.on_call_end:
            r = fn()
            if asyncio.iscoroutine(r):
                await r
        await self.broadcast("call", {"state": "ended"})
        log.info("call ended, window cleared")

    # ------------------------------------------------------------ chunks
    async def feed(self, chunk: TranscriptChunk) -> None:
        if not self.active:
            await self.start_call()
        self.window.append(chunk)
        self._prune()
        await self.broadcast("transcript", chunk)
        if chunk["speaker"] == "caller":
            self.request_check()

    def request_check(self) -> None:
        if self._task and not self._task.done():
            self._pending = True  # skip-if-busy; one rerun later
            return
        self._task = asyncio.get_running_loop().create_task(self._run_checks())

    async def _run_checks(self) -> None:
        loop = asyncio.get_running_loop()
        call_id = self.call_id
        while True:
            self._pending = False
            text = window_text(self.window)
            if not text:
                return
            t0 = time.monotonic()
            try:
                result = await loop.run_in_executor(self._executor, self.check_fn, text, self.rules)
            except Exception as e:
                log.warning("check failed: %s", type(e).__name__)
                result = None
            log.info("check %.2fs, window %d chunks, risk %s",
                     time.monotonic() - t0, len(self.window), result and result.get("risk"))
            if call_id != self.call_id:
                return  # the call ended while we were checking
            if result is not None:
                shown = self.call_risk.update(result)
                await self.broadcast("check", shown)
                for fn in self.on_check:
                    r = fn(result, shown)
                    if asyncio.iscoroutine(r):
                        await r
            if not self._pending:
                return

    async def drain(self) -> None:
        """Wait for any running (and pending) check to finish."""
        while self._task and not self._task.done():
            await self._task

    # ------------------------------------------------------------ streams
    async def run(self, stream: Iterator[TranscriptChunk]) -> None:
        """Consume a blocking chunk generator (audio or fake) without blocking the loop."""
        end = object()
        it = iter(stream)
        self._stop = False
        try:
            while not self._stop:
                chunk = await asyncio.to_thread(next, it, end)
                if chunk is end or self._stop:
                    break
                await self.feed(chunk)  # type: ignore[arg-type]
            await self.drain()
            if self.active:
                for fn in self.on_stream_end:
                    result = fn()
                    if asyncio.iscoroutine(result):
                        await result
        finally:
            await self.end_call()

    async def run_live(self, make_stream: Callable[[], Iterable[TranscriptChunk]],
                       idle_s: float = CALL_IDLE_S) -> None:
        """Consume live audio until the stream stops (device lost, app quit).

        Unlike a replay, `end_call` does not stop the stream: the next chunk
        starts a new call. A call also ends after `idle_s` with no speech.
        The audio generator runs in a daemon thread so quitting never waits on it.
        """
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue = asyncio.Queue()
        end = object()

        def reader() -> None:
            try:
                for chunk in make_stream():
                    loop.call_soon_threadsafe(queue.put_nowait, chunk)
            except Exception as e:  # missing device, sounddevice not installed, ...
                log.warning("live audio stopped: %s", type(e).__name__)
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, end)

        threading.Thread(target=reader, name="audio", daemon=True).start()
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(queue.get(), idle_s if self.active else None)
                except asyncio.TimeoutError:
                    log.info("no speech for %.0fs, ending call", idle_s)
                    await self._finish_stream()
                    continue
                if chunk is end:
                    break
                await self.feed(chunk)  # type: ignore[arg-type]
            await self._finish_stream()
        finally:
            await self.end_call()

    async def _finish_stream(self) -> None:
        await self.drain()
        if self.active:
            for fn in self.on_stream_end:
                result = fn()
                if asyncio.iscoroutine(result):
                    await result
        await self.end_call()

    async def run_fake(self, path: str | Path, speed: float = 1.0) -> None:
        await self.run(load_fake_stream()(path, speed=speed))

    def close(self) -> None:
        self.clear()
        self._executor.shutdown(wait=False, cancel_futures=True)
