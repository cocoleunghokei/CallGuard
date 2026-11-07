"""Replay an English scenario script as call-relative transcript chunks."""

from collections.abc import Iterator
from math import isfinite
from pathlib import Path
from time import monotonic, sleep

from callguard.shared.contracts import TranscriptChunk


CHUNK_SECONDS = 3.0


def fake_stream(path: str | Path, speed: float = 1.0) -> Iterator[TranscriptChunk]:
    """Yield one chunk per script line in 3-second call slots.

    ``speed`` scales wall-clock replay only. The chunk timestamps always describe
    the original call, so the server's rolling window works at any replay speed.
    ``speed=0`` yields immediately for tests and evaluation.
    """
    if not isfinite(speed) or speed < 0:
        raise ValueError("speed must be a finite, non-negative number")

    call_start = monotonic()
    utterance_index = 0
    for line_number, raw_line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), 1):
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue

        speaker, separator, text = line.partition(":")
        if not separator or speaker not in ("caller", "you") or not text.strip():
            raise ValueError(f"invalid script utterance on line {line_number}")

        start = utterance_index * CHUNK_SECONDS
        end = start + CHUNK_SECONDS
        utterance_index += 1
        if speed:
            remaining = call_start + end / speed - monotonic()
            if remaining > 0:
                sleep(remaining)

        yield TranscriptChunk(
            speaker=speaker,
            text=text.strip(),
            start=start,
            end=end,
            language="en",
        )
