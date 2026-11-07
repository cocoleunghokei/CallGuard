"""Call audio capture, transcription, and script replay."""

from .fake import fake_stream
from .stream import stream_chunks

__all__ = ["fake_stream", "stream_chunks"]
