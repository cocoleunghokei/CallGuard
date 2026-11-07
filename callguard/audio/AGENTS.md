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
- [ ] Continuity calls, only if the test passed
- [x] AUD-9 `audio_ok()` and `audio_health()` check device readiness and optional in-memory signal peaks (Server status/UI wiring pending)

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
