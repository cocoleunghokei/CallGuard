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


# AUD-8: Continuity calls go through FaceTime, which can move the Mac's sound
# output away from the Multi-Output Device; the caller then never reaches BlackHole.

def output_devices(output_name):
    return [
        {"name": "BlackHole 2ch", "max_input_channels": 2},
        {"name": "MacBook Pro Microphone", "max_input_channels": 1},
        {"name": output_name, "max_input_channels": 0},
    ]


def no_peaks(monkeypatch):
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": None, "you": None})


def test_multi_output_route_has_no_warning(monkeypatch):
    fake_sounddevice(monkeypatch, devices=output_devices("Multi-Output Device"))
    sd = sys.modules["sounddevice"]
    sd.default.device = (1, 2)
    no_peaks(monkeypatch)

    result = health.audio_health()
    assert result.ok and result.route_warning is None
    assert result.message == "Audio inputs are ready."


def test_facetime_switching_output_to_speakers_warns_without_blocking(monkeypatch):
    fake_sounddevice(monkeypatch, devices=output_devices("MacBook Pro Speakers"))
    sys.modules["sounddevice"].default.device = (1, 2)
    no_peaks(monkeypatch)

    result = health.audio_health()
    assert result.ok  # the mic still works; the warning is advisory
    assert "MacBook Pro Speakers" in result.route_warning
    assert "Multi-Output Device" in result.message
    assert health.main([]) == 1


def test_bluetooth_output_warns_that_it_skips_blackhole(monkeypatch):
    fake_sounddevice(monkeypatch, devices=output_devices("Coco's AirPods Pro"))
    sys.modules["sounddevice"].default.device = (1, 2)
    no_peaks(monkeypatch)

    assert "skips BlackHole" in health.audio_health().route_warning


def test_renamed_multi_output_and_custom_caller_routes_skip_the_warning(monkeypatch):
    fake_sounddevice(monkeypatch, devices=output_devices("Callguard Out"))
    sys.modules["sounddevice"].default.device = (1, 2)
    no_peaks(monkeypatch)
    assert health.audio_health().route_warning is not None

    monkeypatch.setenv("CALLGUARD_OUTPUT_DEVICE", "callguard out")
    assert health.audio_health().route_warning is None

    monkeypatch.delenv("CALLGUARD_OUTPUT_DEVICE")
    monkeypatch.setenv("CALLGUARD_CALLER_DEVICE", "MacBook Pro Microphone")  # speakerphone route
    assert health.audio_health().route_warning is None


def test_silent_caller_during_speech_test_explains_the_route(monkeypatch):
    fake_sounddevice(monkeypatch, devices=output_devices("MacBook Pro Speakers"))
    sys.modules["sounddevice"].default.device = (1, 2)
    monkeypatch.setattr(health, "signal_peaks", lambda: {"caller": 0.0, "you": 0.02})

    result = health.audio_health(require_signal=True)
    assert not result.ok
    assert "MacBook Pro Speakers" in result.message


def test_call_check_prints_results_table_row(monkeypatch, capsys):
    import numpy as np
    from callguard.audio.capture import AudioChunk

    fake_sounddevice(monkeypatch)
    levels = {"caller": None, "you": None}
    monkeypatch.setattr(health, "signal_peaks", lambda: levels.copy())

    def fake_capture(duration):
        assert duration == 5
        levels.update(caller=0.071, you=0.0)
        yield AudioChunk("caller", np.full(48_000, 0.071, dtype=np.float32), 0.0, 3.0)

    monkeypatch.setattr(health, "capture_chunks", fake_capture)
    assert health.main(["--call", "5"]) == 1  # mic was silent

    out = capsys.readouterr().out
    assert "caller: rms=0.0710" in out
    assert "No mic sound heard" in out
    assert "| Continuity (Mac speakers) | ✅ level 0.071 | ❌ level 0.000 | | |" in out
