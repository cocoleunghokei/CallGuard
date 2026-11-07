"""Read-only health checks for Callguard's two local audio inputs."""

from __future__ import annotations

from dataclasses import dataclass

from .capture import SAMPLE_RATE, _selected_input_devices, signal_peaks
from .transcribe import SILENCE_RMS


@dataclass(frozen=True)
class AudioHealth:
    ok: bool
    message: str
    caller_rms: float | None = None
    mic_rms: float | None = None


def audio_health(require_signal: bool = False) -> AudioHealth:
    """Check device readiness, optionally requiring recent speech-test levels.

    Silence during an idle or paused call is normal. Only a supervised speaking
    test should set ``require_signal=True``.
    """
    levels = signal_peaks()
    caller_rms, mic_rms = levels["caller"], levels["you"]
    try:
        import sounddevice as sd  # the app and offline tests can import without it
    except ImportError:
        return AudioHealth(False, "Audio capture is unavailable. Install sounddevice.", caller_rms, mic_rms)

    try:
        caller_device, mic_device = _selected_input_devices(sd)
    except RuntimeError as exc:
        return AudioHealth(False, str(exc), caller_rms, mic_rms)
    except Exception:
        return AudioHealth(False, "Could not check audio input devices.", caller_rms, mic_rms)

    for speaker, device in (("caller", caller_device), ("you", mic_device)):
        try:
            sd.check_input_settings(device=device, samplerate=SAMPLE_RATE, channels=1, dtype="float32")
        except Exception:
            label = "BlackHole caller audio" if speaker == "caller" else "microphone audio"
            return AudioHealth(False, f"Cannot open {label} at 16 kHz. Check the input device.", caller_rms, mic_rms)

    if require_signal:
        if caller_rms is None or caller_rms < SILENCE_RMS:
            return AudioHealth(False, "No caller sound heard. Check the call app's output route.", caller_rms, mic_rms)
        if mic_rms is None or mic_rms < SILENCE_RMS:
            return AudioHealth(False, "No mic sound heard. Check the microphone input.", caller_rms, mic_rms)
    return AudioHealth(True, "Audio inputs are ready.", caller_rms, mic_rms)


def audio_ok(require_signal: bool = False) -> bool:
    """Boolean form of :func:`audio_health` for a Server status probe."""
    return audio_health(require_signal=require_signal).ok


def main() -> int:
    result = audio_health()
    print(result.message)
    return 0 if result.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
