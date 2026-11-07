"""Capture caller and microphone audio in memory, one 3-second chunk at a time."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os
from queue import Empty, Full, Queue
from time import monotonic
from typing import TYPE_CHECKING, Iterator

from callguard.shared.contracts import Speaker

if TYPE_CHECKING:
    from numpy import ndarray


SAMPLE_RATE = 16_000
CHUNK_SECONDS = 3
CHUNK_FRAMES = SAMPLE_RATE * CHUNK_SECONDS


@dataclass(frozen=True)
class AudioChunk:
    speaker: Speaker
    samples: ndarray  # float32 mono; owned copy of sounddevice's callback buffer
    start: float  # seconds since capture began
    end: float


def _input_device(sd: object, name: str | None, source: str) -> int:
    devices = sd.query_devices()
    if name is None:
        device = sd.default.device[0]
        if device is None or device < 0 or devices[device]["max_input_channels"] < 1:
            raise RuntimeError("No default input microphone is available")
        return device

    for index, device in enumerate(devices):
        if name.casefold() in device["name"].casefold() and device["max_input_channels"] >= 1:
            return index
    raise RuntimeError(f"{source} input device matching {name!r} was not found")


def capture_chunks(duration: float | None = None) -> Iterator[AudioChunk]:
    """Yield mono float32 audio from both inputs while the streams are open.

    A bounded queue keeps the callback nonblocking. If transcription falls behind,
    the oldest queued audio is dropped so on-screen words stay current.
    """
    import sounddevice as sd  # local import: offline tests and script replay need no device

    caller_name = os.environ.get("CALLGUARD_CALLER_DEVICE") or "BlackHole 2ch"
    mic_name = os.environ.get("CALLGUARD_MIC_DEVICE") or None
    caller_device = _input_device(sd, caller_name, "Caller")
    mic_device = _input_device(sd, mic_name, "Mic")
    chunks: Queue[AudioChunk] = Queue(maxsize=4)
    frames_seen = {"caller": 0, "you": 0}

    def callback_for(speaker: Speaker):
        def callback(indata, frames, time_info, status):
            start = frames_seen[speaker] / SAMPLE_RATE
            frames_seen[speaker] += frames
            chunk = AudioChunk(speaker, indata[:, 0].copy(), start, frames_seen[speaker] / SAMPLE_RATE)
            try:
                chunks.put_nowait(chunk)
            except Full:
                try:
                    chunks.get_nowait()
                except Empty:
                    pass
                try:
                    chunks.put_nowait(chunk)
                except Full:
                    pass

        return callback

    caller_stream = sd.InputStream(
        device=caller_device, samplerate=SAMPLE_RATE, channels=1,
        dtype="float32", blocksize=CHUNK_FRAMES, callback=callback_for("caller"),
    )
    mic_stream = sd.InputStream(
        device=mic_device, samplerate=SAMPLE_RATE, channels=1,
        dtype="float32", blocksize=CHUNK_FRAMES, callback=callback_for("you"),
    )
    with caller_stream, mic_stream:
        deadline = None if duration is None else monotonic() + duration
        while True:
            remaining = None if deadline is None else deadline - monotonic()
            if remaining is not None and remaining <= 0:
                return
            try:
                yield chunks.get(timeout=0.5 if remaining is None else min(0.5, remaining))
            except Empty:
                continue


def rms(samples: ndarray) -> float:
    """Root mean square level of one in-memory audio chunk."""
    import numpy as np

    return float(np.sqrt(np.mean(np.square(samples, dtype=np.float64))))


def main() -> int:
    parser = argparse.ArgumentParser(description="Callguard audio capture routing check")
    parser.add_argument("--rms", action="store_true", help="print each source's RMS for 10 seconds")
    args = parser.parse_args()
    if not args.rms:
        parser.print_help()
        return 0

    try:
        for chunk in capture_chunks(duration=10):
            print(f"{chunk.speaker}: rms={rms(chunk.samples):.4f}", flush=True)
    except (ImportError, RuntimeError) as exc:
        parser.exit(1, f"Capture unavailable: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
