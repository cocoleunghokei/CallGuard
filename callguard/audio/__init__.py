"""Call audio capture, transcription, and script replay."""

from collections.abc import Iterator

from callguard.shared.contracts import TranscriptChunk

from .fake import fake_stream


def stream_chunks() -> Iterator[TranscriptChunk]:
    """Start the live stream only when the caller iterates it."""
    from .stream import stream_chunks as _stream_chunks

    yield from _stream_chunks()

__all__ = ["fake_stream", "stream_chunks"]
