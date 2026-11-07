"""Turn the two live audio inputs into transcript chunks for the server."""

from __future__ import annotations

from collections.abc import Iterator
from contextlib import closing

from callguard.shared.contracts import TranscriptChunk

from .capture import capture_chunks
from .transcribe import get_model, transcribe_chunk


def stream_chunks() -> Iterator[TranscriptChunk]:
    """Yield nonempty English transcripts with capture-relative timestamps.

    Warm Whisper before opening the inputs so model initialization does not
    delay the first spoken chunk. Closing this generator closes both streams.
    """
    get_model()
    with closing(capture_chunks()) as audio_chunks:
        for audio in audio_chunks:
            text = transcribe_chunk(audio.samples)
            if text:
                yield TranscriptChunk(
                    speaker=audio.speaker,
                    text=text,
                    start=audio.start,
                    end=audio.end,
                    language="en",
                )
