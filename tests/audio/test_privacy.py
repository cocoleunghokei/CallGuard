"""Privacy boundary: neither replay nor live transcription may write call data."""

import builtins
import io
import os
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import numpy as np

from callguard.audio import fake_stream, stream_chunks, transcribe
from callguard.audio.capture import AudioChunk


def test_replay_and_live_stream_make_no_file_writes(monkeypatch, tmp_path):
    model_dir = tmp_path / "small"
    model_dir.mkdir()  # test setup happens before writes are blocked
    monkeypatch.setenv("CALLGUARD_WHISPER_DIR", str(model_dir))
    transcribe.get_model.cache_clear()

    class FakeWhisperModel:
        def __init__(self, *args, **kwargs):
            pass

        def transcribe(self, samples, **kwargs):
            return iter([SimpleNamespace(text=" spoken words ")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    soundfile = ModuleType("soundfile")

    def reject_soundfile_write(*args, **kwargs):
        raise AssertionError("soundfile.write called")

    soundfile.write = reject_soundfile_write
    monkeypatch.setitem(sys.modules, "soundfile", soundfile)

    def fake_capture():
        yield AudioChunk("caller", np.full(48_000, 0.01, dtype=np.float32), 0.0, 3.0)

    monkeypatch.setattr("callguard.audio.stream.capture_chunks", fake_capture)
    real_open = builtins.open
    real_io_open = io.open
    real_os_open = os.open

    def read_only(open_fn):
        def checked(path, mode="r", *args, **kwargs):
            if any(flag in mode for flag in "wax+"):
                raise AssertionError(f"file write attempted: {path}")
            return open_fn(path, mode, *args, **kwargs)
        return checked

    def checked_os_open(path, flags, *args, **kwargs):
        if flags & (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND):
            raise AssertionError(f"file write attempted: {path}")
        return real_os_open(path, flags, *args, **kwargs)

    try:
        with monkeypatch.context() as guard:
            guard.setattr(builtins, "open", read_only(real_open))
            guard.setattr(io, "open", read_only(real_io_open))
            guard.setattr(os, "open", checked_os_open)

            script = Path(__file__).parent / "fixtures" / "one_caller.txt"
            assert len(list(fake_stream(script, speed=0))) == 1
            assert list(stream_chunks()) == [
                {"speaker": "caller", "text": "spoken words", "start": 0.0, "end": 3.0, "language": "en"}
            ]
    finally:
        transcribe.get_model.cache_clear()
