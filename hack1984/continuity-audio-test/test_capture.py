"""
Continuity call audio test.
Records the caller (via BlackHole) and you (via the Mac mic) at the same time,
saves two WAV files, and transcribes them locally if faster-whisper is installed.

Setup:  pip3 install sounddevice soundfile numpy faster-whisper
Run:    python3 test_capture.py            (records 20 seconds)
        python3 test_capture.py 40         (records 40 seconds)
"""
import sys, threading
import numpy as np
import sounddevice as sd
import soundfile as sf

SECONDS = int(sys.argv[1]) if len(sys.argv) > 1 else 20
RATE = 16000

def find(name_part, need_input=True):
    for i, d in enumerate(sd.query_devices()):
        if name_part.lower() in d["name"].lower() and (d["max_input_channels"] > 0 or not need_input):
            return i
    return None

print("Audio devices on this Mac:")
print(sd.query_devices())

bh = find("BlackHole")
mic = sd.default.device[0]
if bh is None:
    sys.exit("\nBlackHole not found. Install it: brew install blackhole-2ch, then restart the Mac's audio (or reboot).")

print(f"\nCaller source: {sd.query_devices(bh)['name']}")
print(f"Your mic:      {sd.query_devices(mic)['name']}")
print(f"\nStart the call now. Recording {SECONDS} seconds...\n")

results = {}
def rec(dev, key):
    results[key] = sd.rec(int(SECONDS * RATE), samplerate=RATE, channels=1, device=dev, dtype="float32")

threads = [threading.Thread(target=rec, args=(bh, "caller")), threading.Thread(target=rec, args=(mic, "you"))]
for t in threads: t.start()
sd.wait()
for t in threads: t.join()

for key, audio in results.items():
    sf.write(f"{key}.wav", audio, RATE)
    level = float(np.sqrt(np.mean(audio ** 2)))
    verdict = "HEARD SOUND" if level > 0.003 else "SILENT (capture failed)"
    print(f"{key}.wav  level={level:.4f}  -> {verdict}")

try:
    from faster_whisper import WhisperModel
    print("\nTranscribing locally (no internet needed after first model download)...")
    model = WhisperModel("base", compute_type="int8")
    for key in ("caller", "you"):
        segs, info = model.transcribe(f"{key}.wav")
        print(f"\n[{key}] ({info.language}): " + " ".join(s.text.strip() for s in segs))
except ImportError:
    print("\nfaster-whisper not installed, skipped transcription. Play caller.wav to check.")
