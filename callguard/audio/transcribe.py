"""Offline, in-memory English transcription for 16 kHz mono audio chunks."""

from __future__ import annotations

import argparse
from functools import lru_cache
import os
from pathlib import Path
from time import monotonic
from typing import TYPE_CHECKING

from .capture import capture_chunks, rms

if TYPE_CHECKING:
    from numpy import ndarray


SILENCE_RMS = 0.003


@lru_cache(maxsize=1)
def get_model():
    """Load the pre-downloaded small model once, with Hub access disabled."""
    model_dir = os.environ.get("CALLGUARD_WHISPER_DIR")
    if not model_dir or not Path(model_dir).is_dir():
        raise RuntimeError("CALLGUARD_WHISPER_DIR must point to the local faster-whisper small model directory")

    os.environ["HF_HUB_OFFLINE"] = "1"
    from faster_whisper import WhisperModel  # local import: fake replay needs no model

    return WhisperModel(model_dir, device="cpu", compute_type="int8", local_files_only=True)


def transcribe_chunk(samples: ndarray) -> str:
    """Return recognized English words, or an empty string for silence."""
    if rms(samples) < SILENCE_RMS:
        return ""

    segments, _ = get_model().transcribe(
        samples,
        language="en",
        vad_filter=True,
        beam_size=1,
        condition_on_previous_text=False,
    )
    return " ".join(segment.text.strip() for segment in segments if segment.text.strip())


def main() -> int:
    parser = argparse.ArgumentParser(description="Check local Whisper transcription from both inputs")
    parser.add_argument("--check", action="store_true", help="capture both sources and print timing plus an 80-character transcript tail")
    parser.add_argument("--seconds", type=int, default=10, metavar="N", help="capture duration in seconds (default: 10)")
    args = parser.parse_args()
    if args.seconds <= 0:
        parser.error("--seconds must be positive")
    if not args.check:
        parser.print_help()
        return 0

    try:
        get_model()  # warm the model before the timed audio check
        for chunk in capture_chunks(duration=args.seconds):
            started = monotonic()
            text = transcribe_chunk(chunk.samples)
            elapsed_ms = (monotonic() - started) * 1_000
            tail = text.replace("\n", " ")[-80:]
            print(f"{chunk.speaker}: rms={rms(chunk.samples):.4f} transcribe_ms={elapsed_ms:.0f} tail={tail}", flush=True)
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f"Transcription unavailable: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
