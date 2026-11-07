"""Call audio capture, transcription, and script replay."""

from collections.abc import Iterator

from callguard.shared.contracts import TranscriptChunk

from .fake import fake_stream


def stream_chunks() -> Iterator[TranscriptChunk]:
    """Start the live stream only when the caller iterates it."""
    from .stream import stream_chunks as _stream_chunks

    yield from _stream_chunks()


def audio_health(require_signal: bool = False):
    """Return readiness and a plain-language audio warning if needed."""
    from .health import audio_health as _audio_health

    return _audio_health(require_signal=require_signal)


def audio_ok(require_signal: bool = False) -> bool:
    """Boolean form of the local audio health check."""
    return audio_health(require_signal=require_signal).ok


__all__ = ["fake_stream", "stream_chunks", "audio_health", "audio_ok"]
