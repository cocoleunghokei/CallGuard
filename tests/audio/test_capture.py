import sys
from types import SimpleNamespace

import numpy as np
import pytest

from callguard.audio import capture


class FakeInputStream:
    opened = []

    def __init__(self, **kwargs):
        self.kwargs = kwargs

    def __enter__(self):
        self.opened.append(self)
        self.kwargs["callback"](
            np.ones((capture.CHUNK_FRAMES, 1), dtype=np.float32),
            capture.CHUNK_FRAMES, None, None,
        )
        return self

    def __exit__(self, *args):
        return False


def test_capture_uses_two_16khz_mono_float32_streams(monkeypatch):
    FakeInputStream.opened = []
    devices = [
        {"name": "BlackHole 2ch", "max_input_channels": 2},
        {"name": "Built-in Microphone", "max_input_channels": 1},
    ]
    fake_sd = SimpleNamespace(
        query_devices=lambda: devices,
        default=SimpleNamespace(device=(1, 0)),
        InputStream=FakeInputStream,
    )
    monkeypatch.setitem(sys.modules, "sounddevice", fake_sd)
    monkeypatch.delenv("CALLGUARD_CALLER_DEVICE", raising=False)
    monkeypatch.delenv("CALLGUARD_MIC_DEVICE", raising=False)

    chunks = list(capture.capture_chunks(duration=0.01))

    assert [chunk.speaker for chunk in chunks] == ["caller", "you"]
    assert [(chunk.start, chunk.end) for chunk in chunks] == [(0.0, 3.0), (0.0, 3.0)]
    assert all(chunk.samples.shape == (capture.CHUNK_FRAMES,) for chunk in chunks)
    assert all(chunk.samples.dtype == np.float32 for chunk in chunks)
    assert [stream.kwargs["device"] for stream in FakeInputStream.opened] == [0, 1]
    assert all(stream.kwargs["samplerate"] == 16_000 for stream in FakeInputStream.opened)
    assert all(stream.kwargs["channels"] == 1 for stream in FakeInputStream.opened)
    assert all(stream.kwargs["dtype"] == "float32" for stream in FakeInputStream.opened)
    assert all(stream.kwargs["blocksize"] == 48_000 for stream in FakeInputStream.opened)
    assert capture.rms(chunks[0].samples) == pytest.approx(1.0)
    assert capture.signal_peaks() == {"caller": pytest.approx(1.0), "you": pytest.approx(1.0)}


def test_device_name_overrides(monkeypatch):
    devices = [
        {"name": "BlackHole 2ch", "max_input_channels": 2},
        {"name": "USB Microphone", "max_input_channels": 1},
        {"name": "Built-in Microphone", "max_input_channels": 1},
    ]
    sd = SimpleNamespace(query_devices=lambda: devices, default=SimpleNamespace(device=(2, 0)))
    assert capture._input_device(sd, "blackhole", "Caller") == 0
    assert capture._input_device(sd, "USB", "Mic") == 1
    assert capture._input_device(sd, None, "Mic") == 2
    with pytest.raises(RuntimeError, match="Caller input device"):
        capture._input_device(sd, "missing", "Caller")
