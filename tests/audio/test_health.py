import sys
from types import SimpleNamespace

from callguard.audio import audio_ok, health


def fake_sounddevice(monkeypatch, devices=None, default_mic=1, failed_input=None):
    if devices is None:
        devices = [
            {"name": "BlackHole 2ch", "max_input_channels": 2},
            {"name": "MacBook Pro Microphone", "max_input_channels": 1},
        ]

    def check_input_settings(**kwargs):
        if kwargs["device"] == failed_input:
            raise RuntimeError("PortAudio rejected input")
        assert kwargs["samplerate"] == 16_000
        assert kwargs["channels"] == 1
        assert kwargs["dtype"] == "float32"

    monkeypatch.setitem(sys.modules, "sounddevice", SimpleNamespace(
        query_devices=lambda: devices,
        default=SimpleNamespace(device=(default_mic, 0)),
        check_input_settings=check_input_settings,
    ))


def test_audio_health_reports_ready_inputs(monkeypatch):
    fake_sounddevice(monkeypatch)
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": None, "you": None})

    result = health.audio_health()
    assert result.ok
    assert result.message == "Audio inputs are ready."
    assert audio_ok()


def test_unplugged_blackhole_returns_plain_warning(monkeypatch):
    fake_sounddevice(monkeypatch, devices=[{"name": "MacBook Pro Microphone", "max_input_channels": 1}], default_mic=0)
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": None, "you": None})

    result = health.audio_health()
    assert not result.ok
    assert "BlackHole 2ch" in result.message
    assert not audio_ok()


def test_missing_or_unopenable_mic_returns_warning(monkeypatch):
    fake_sounddevice(monkeypatch, default_mic=-1)
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": None, "you": None})
    assert health.audio_health().message == "No default input microphone is available"

    fake_sounddevice(monkeypatch, failed_input=1)
    assert health.audio_health().message == "Cannot open microphone audio at 16 kHz. Check the input device."


def test_speech_test_can_check_both_signal_levels_without_flagging_idle_silence(monkeypatch):
    fake_sounddevice(monkeypatch)
    levels = {"caller": 0.0, "you": 0.02}
    monkeypatch.setattr(health, "signal_peaks", lambda: levels.copy())

    assert audio_ok()  # silence while idle is not a missing-device warning
    assert not audio_ok(require_signal=True)
    assert "No caller sound" in health.audio_health(require_signal=True).message
    levels["caller"] = 0.04
    assert audio_ok(require_signal=True)


def test_health_does_not_require_sounddevice_to_import(monkeypatch):
    monkeypatch.setitem(sys.modules, "sounddevice", None)
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": None, "you": None})
    result = health.audio_health()
    assert not result.ok
    assert "Install sounddevice" in result.message
