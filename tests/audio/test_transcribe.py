import os
import sys
from types import SimpleNamespace

import numpy as np
import pytest

from callguard.audio import transcribe


def test_silence_never_loads_model(monkeypatch):
    transcribe.get_model.cache_clear()
    monkeypatch.delenv("CALLGUARD_WHISPER_DIR", raising=False)
    assert transcribe.transcribe_chunk(np.zeros(48_000, dtype=np.float32)) == ""
    assert transcribe.transcribe_chunk(np.full(48_000, 0.002, dtype=np.float32)) == ""


def test_model_is_local_loaded_once_and_english_vad_is_fixed(monkeypatch, tmp_path):
    model_dir = tmp_path / "small"
    model_dir.mkdir()
    monkeypatch.setenv("CALLGUARD_WHISPER_DIR", str(model_dir))
    monkeypatch.delenv("HF_HUB_OFFLINE", raising=False)
    created = []

    class FakeWhisperModel:
        def __init__(self, path, **kwargs):
            created.append((path, kwargs, os.environ.get("HF_HUB_OFFLINE")))

        def transcribe(self, samples, **kwargs):
            assert samples.dtype == np.float32
            assert kwargs == {
                "language": "en", "vad_filter": True, "beam_size": 1,
                "condition_on_previous_text": False,
            }
            return iter([SimpleNamespace(text=" Hello "), SimpleNamespace(text=" there ")]), None

    monkeypatch.setitem(sys.modules, "faster_whisper", SimpleNamespace(WhisperModel=FakeWhisperModel))
    transcribe.get_model.cache_clear()
    speech = np.full(48_000, 0.01, dtype=np.float32)
    assert transcribe.transcribe_chunk(speech) == "Hello there"
    assert transcribe.transcribe_chunk(speech) == "Hello there"
    assert created == [(str(model_dir), {"device": "cpu", "compute_type": "int8", "local_files_only": True}, "1")]
    transcribe.get_model.cache_clear()


def test_missing_local_model_fails_without_importing_whisper(monkeypatch):
    monkeypatch.delenv("CALLGUARD_WHISPER_DIR", raising=False)
    transcribe.get_model.cache_clear()
    with pytest.raises(RuntimeError, match="CALLGUARD_WHISPER_DIR"):
        transcribe.get_model()
