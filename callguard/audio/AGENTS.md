# Lane: Audio + transcription

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/audio/` and `tests/audio/` only.

## Delivers
`stream_chunks()`: a generator that yields a `TranscriptChunk` (see `callguard/shared/contracts.py`) about every 3 s, for both the caller and you.

## Tasks
**P0**
- [ ] Continuity test, Sat 12:30 ([plan section 5](../../hack1984/project-plan.md)). Record the results in the plan's table
- [x] `capture.py`: read the caller from BlackHole 2ch and you from the mic with `sounddevice`, at 16 kHz mono, in 3 s chunks. Start from [test_capture.py](../../hack1984/continuity-audio-test/test_capture.py)
- [x] `transcribe.py`: faster-whisper `small`, int8. Load the model once, transcribe each chunk, skip silent chunks
- [x] `stream_chunks()` combining both, plus `fake_stream(script_path)` that replays a written script, for the other lanes and for tests

**P1**
- [ ] AUD-8 Continuity calls, only if the test passed. Code side done: the output-route warning in `audio_health()` and the supervised `--call` check (see **Continuity calls** below). Stays open until a real iPhone call answered on the Mac transcribes
- [x] AUD-9 `audio_ok()` and `audio_health()` check device readiness and optional in-memory signal peaks (Server status/UI wiring pending)

## Continuity calls (AUD-8)
An iPhone call answered on the Mac plays through FaceTime. Capture uses the same route as Zoom: system output → **Multi-Output Device** (speakers + BlackHole 2ch) → `capture.py` reads BlackHole as `caller`. What can go wrong, and what catches it:
- FaceTime moves the output off Multi-Output (now or mid-call): `audio_health()` sets `route_warning` ("Sound goes to MacBook Pro Speakers…"). It is advisory: `ok` stays true because the mic still works. A renamed Multi-Output Device can be named in `CALLGUARD_OUTPUT_DEVICE`. A custom `CALLGUARD_CALLER_DEVICE` that is not BlackHole (speakerphone route) skips the check
- AirPods/Bluetooth output skips BlackHole: same warning, with "use the Mac speakers"
- FaceTime holds the mic: the supervised check reports "No mic sound heard…" with the FaceTime → Video → Microphone hint
- PortAudio reads the device list once per process, so the route is checked at app start and on each status retry, not live mid-call. A mid-call switch shows up as a silent caller in the supervised check

Hardware test (plan §5, about 5 min), nothing is saved:
```bash
python -m callguard.audio.health                   # devices + output route; exit 1 on any warning
python -m callguard.audio.health --call 30         # answer the iPhone call on the Mac and speak
python -m callguard.audio.health --call 30 --route "Zoom (Mac speakers)"   # other rows
python -m callguard.audio.transcribe --check --seconds 30   # transcript column (80-char tail)
```
`--call` prints a row ready to paste into the plan's results table, e.g. `| Continuity (Mac speakers) | ✅ level 0.071 | ✅ level 0.004 | | |`.

## Rules for this lane
- Audio stays in memory. Never call `sf.write` or save a WAV outside the standalone test script
- Never print full transcripts
- Target: words appear within ~3 s of being spoken

## Status
- [Sat 16:50] Done: AUD-5 fake_stream with 3 s call slots, instant replay, fixtures, and 5 passing offline tests | Next: AUD-2 capture.py after Coco reviews this checkpoint | Needs: Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt and pre-download the Whisper small model
- [Sat 17:31] Done: AUD-2 two in-memory sounddevice InputStreams (BlackHole 2ch and default mic), 16 kHz mono float32 3 s queue, device name overrides, 10 s `--rms` mode; 7 audio tests pass with fake devices | Next: AUD-3 transcribe.py after Coco reviews this checkpoint | Needs: Coco to run `python -m callguard.audio.capture --rms` on the Mac during a call and confirm caller/you RMS routing; pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt and pre-download Whisper small
- [Sat 17:34] Done: AUD-3 offline faster-whisper small int8 loaded once from CALLGUARD_WHISPER_DIR, English VAD, RMS silence skip, 10 s `--check` timing/tail mode; 10 audio tests pass offline | Next: AUD-4 stream_chunks() after Coco reviews this checkpoint | Needs: Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt, pre-download the faster-whisper small model, set CALLGUARD_WHISPER_DIR to its directory, and run the Mac capture/transcription checks
- [Sat 17:46] Done: AUD-4 stream_chunks() exports both speakers as TranscriptChunk, skips empty speech, warms Whisper before capture, closes capture on generator close; 12 audio tests pass offline | Next: AUD-6 privacy/no-write tests after Coco reviews this checkpoint | Needs: Server lane to wire callguard.audio.stream_chunks() into the live (non--fake) path; Coco to run Mac routing/transcription checks and pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt
- [Sat 17:49] Done: AUD-4 follow-up makes stream_chunks import lazy, removing `python -m callguard.audio.capture` and `.transcribe` runpy warnings; 12 audio tests pass | Next: AUD-6 privacy/no-write tests | Needs: Coco to install sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in the Mac test venv and set CALLGUARD_WHISPER_DIR to the actual cached small-model snapshot; Server to wire the live stream
- [Sat 17:58] Done: AUD-6 replays all 8 Detection scripts, skips sub-threshold mic audio, and checks fake/live paths with open, os.open, and soundfile.write guarded against writes; 14 audio tests pass offline | Next: Coco review; P0 Audio code complete | Needs: Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt and retest caller audio on a later call; Server to wire stream_chunks() into the live path. Mac mic transcribed at 2.364 s first chunk and 1.175 s second chunk; first exceeds the 1.5 s target
- [Sat 18:03] Done: Mac caller check showed RMS 0.0155 and transcript chunks at 1.337, 1.167, and 1.189 s; added optional `--seconds N` to both CLI checks so caller and mic can speak in one window; 14 audio tests pass offline | Next: Coco review and a 30 s two-speaker check | Needs: Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt; Server to wire stream_chunks() into the live path
- [Sat 18:11] Done: AUD-9 Audio-side health probe (`audio_ok`, `audio_health`): missing BlackHole/mic or unsupported 16 kHz input returns a plain warning, optional supervised signal check uses in-memory peak RMS; 19 audio tests pass offline. Coco's Google Meet run transcribed both speakers at about 1.2 s per speech chunk | Next: Coco review; AUD-8 stays gated on the separate Continuity test | Needs: Coco to add optional `Status.audio_ok` (bool) and `Status.audio_message` (str) to the shared contract, then Server to publish `audio_health()` in status and handle capture startup errors, UI to display its warning; Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt
- [Sun 08:40] Done: AUD-8 code side: `audio_health()` gives an advisory `route_warning` when the Mac's sound output is not a Multi-Output/BlackHole device (FaceTime switched it) or is Bluetooth/AirPods; silent-caller/mic messages now say how to fix the Continuity route; `python -m callguard.audio.health --call N [--route LABEL]` runs a supervised in-memory level check and prints a results-table row; 25 audio tests pass offline (579 in the full suite) | Next: Coco runs `--call 30` on a real iPhone call answered on the Mac; tick AUD-8 only if the caller transcribes | Needs: Coco to fill the Continuity row in plan §5 from the `--call` output, add an optional `Status.audio_warning` (str) to the contract, and add the `health --call` command and `CALLGUARD_OUTPUT_DEVICE` to root AGENTS.md §4; Server to publish `AudioHealth.route_warning` as `audio_warning`; UI to show it as a non-blocking banner (today the banner only shows when `audio_ok` is false)
