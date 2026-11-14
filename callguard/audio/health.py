"""Read-only health checks for Callguard's two local audio inputs.

Also checks the Mac's sound *output* route. Callguard hears the caller only
when the call app plays through a Multi-Output Device that includes BlackHole.
FaceTime (Continuity calls, AUD-8) can switch the output during a call, and
Bluetooth headsets skip BlackHole, so both get a plain-language warning.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
import os

from .capture import SAMPLE_RATE, _selected_input_devices, capture_chunks, rms, signal_peaks
from .transcribe import SILENCE_RMS

_ROUTED_OUTPUTS = ("multi-output", "blackhole")
_BLUETOOTH_OUTPUTS = ("airpods", "bluetooth", "beats")
CALLER_SILENT = (
    "No caller sound heard. During the call, set System Settings → Sound → Output "
    "to the Multi-Output Device (FaceTime can switch it), then retry."
)
MIC_SILENT = (
    "No mic sound heard. The call app may be holding the mic: pick the same mic "
    "in the call app (FaceTime → Video → Microphone) and check Microphone privacy."
)


@dataclass(frozen=True)
class AudioHealth:
    ok: bool
    message: str
    caller_rms: float | None = None
    mic_rms: float | None = None
    route_warning: str | None = None  # advisory: inputs work, but the caller may not reach BlackHole


def output_route_warning(sd: object) -> str | None:
    """Warn when the default sound output cannot be feeding BlackHole.

    Returns None when the route looks right or cannot be judged (custom caller
    device, unknown output). ``CALLGUARD_OUTPUT_DEVICE`` names a renamed
    Multi-Output Device. PortAudio reads the device list once per process, so
    this sees the route as it was when the app (or check) started.
    """
    caller_name = os.environ.get("CALLGUARD_CALLER_DEVICE") or "BlackHole 2ch"
    if "blackhole" not in caller_name.casefold():
        return None  # e.g. speakerphone route: caller comes from another input
    try:
        index = sd.default.device[1]
        devices = sd.query_devices()
        if index is None or index < 0 or index >= len(devices):
            return None
        name = str(devices[index]["name"])
    except Exception:
        return None

    folded = name.casefold()
    expected = (os.environ.get("CALLGUARD_OUTPUT_DEVICE") or "").casefold()
    if (expected and expected in folded) or any(hint in folded for hint in _ROUTED_OUTPUTS):
        return None
    if any(hint in folded for hint in _BLUETOOTH_OUTPUTS):
        return (
            f"Sound goes to {name}, which skips BlackHole, so CallGuard can't hear the caller. "
            "Use the Mac speakers in a Multi-Output Device with BlackHole 2ch."
        )
    return (
        f"Sound goes to {name}, so CallGuard can't hear the caller. In System Settings → Sound → Output, "
        "choose the Multi-Output Device (FaceTime can switch it during a call)."
    )


def audio_health(require_signal: bool = False) -> AudioHealth:
    """Check device readiness, optionally requiring recent speech-test levels.

    Silence during an idle or paused call is normal. Only a supervised speaking
    test should set ``require_signal=True``. A wrong output route does not make
    ``ok`` false (the mic still works and the route may be fine under another
    name); it is reported in ``route_warning`` and in ``message``.
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

    warning = output_route_warning(sd)
    if require_signal:
        if caller_rms is None or caller_rms < SILENCE_RMS:
            return AudioHealth(False, warning or CALLER_SILENT, caller_rms, mic_rms, warning)
        if mic_rms is None or mic_rms < SILENCE_RMS:
            return AudioHealth(False, MIC_SILENT, caller_rms, mic_rms, warning)
    return AudioHealth(True, warning or "Audio inputs are ready.", caller_rms, mic_rms, warning)


def audio_ok(require_signal: bool = False) -> bool:
    """Boolean form of :func:`audio_health` for a Server status probe."""
    return audio_health(require_signal=require_signal).ok


def _level(value: float | None) -> str:
    if value is None:
        return "❌ no audio"
    return f"{'✅' if value >= SILENCE_RMS else '❌'} level {value:.3f}"


def call_check(seconds: int, route: str) -> int:
    """Supervised check during a real call: levels only, nothing kept or saved.

    Prints a row for the results table in the plan (section 5). The transcript
    column stays empty; ``python -m callguard.audio.transcribe --check`` fills it.
    """
    before = audio_health()
    print(before.message, flush=True)
    if not before.ok:
        return 1
    print(f"Start the call now ({route}). Listening {seconds} s; answer on the Mac and speak.", flush=True)
    try:
        for chunk in capture_chunks(duration=seconds):
            print(f"{chunk.speaker}: rms={rms(chunk.samples):.4f}", flush=True)
    except (ImportError, RuntimeError) as exc:
        print(f"Capture unavailable: {exc}")
        return 1

    after = audio_health(require_signal=True)
    print(after.message)
    print(f"| {route} | {_level(after.caller_rms)} | {_level(after.mic_rms)} | | |")
    return 0 if after.ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="CallGuard audio readiness and call-route check")
    parser.add_argument("--call", type=int, metavar="SECONDS",
                        help="listen during a real call for SECONDS and require sound from both sides")
    parser.add_argument("--route", default="Continuity (Mac speakers)",
                        help='label for the results-table row (default: "Continuity (Mac speakers)")')
    args = parser.parse_args(argv)
    if args.call is not None:
        if args.call <= 0:
            parser.error("--call must be positive")
        return call_check(args.call, args.route)

    result = audio_health()
    print(result.message)
    return 0 if result.ok and result.route_warning is None else 1


if __name__ == "__main__":
    raise SystemExit(main())
