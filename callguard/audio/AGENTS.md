# Lane: Audio + transcription

Read the root [AGENTS.md](../../AGENTS.md) first. You own `callguard/audio/` and `tests/audio/` only.

## Delivers
`stream_chunks()`: a generator that yields a `TranscriptChunk` (see `callguard/shared/contracts.py`) about every 3 s, for both the caller and you.

## Tasks
**P0**
- [ ] Continuity test, Sat 12:30 ([plan section 5](../../hack1984/project-plan.md)). Record the results in the plan's table
- [x] `capture.py`: read the caller from BlackHole 2ch and you from the mic with `sounddevice`, at 16 kHz mono, in 3 s chunks. Start from [test_capture.py](../../hack1984/continuity-audio-test/test_capture.py)
- [ ] `transcribe.py`: faster-whisper `small`, int8. Load the model once, transcribe each chunk, skip silent chunks
- [ ] `stream_chunks()` combining both, plus `fake_stream(script_path)` that replays a written script, for the other lanes and for tests

**P1**
- [ ] Continuity calls, only if the test passed

## Rules for this lane
- Audio stays in memory. Never call `sf.write` or save a WAV outside the standalone test script
- Never print full transcripts
- Target: words appear within ~3 s of being spoken

## Status
- [Sat 16:50] Done: AUD-5 fake_stream with 3 s call slots, instant replay, fixtures, and 5 passing offline tests | Next: AUD-2 capture.py after Coco reviews this checkpoint | Needs: Coco to pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt and pre-download the Whisper small model
- [Sat 17:31] Done: AUD-2 two in-memory sounddevice InputStreams (BlackHole 2ch and default mic), 16 kHz mono float32 3 s queue, device name overrides, 10 s `--rms` mode; 7 audio tests pass with fake devices | Next: AUD-3 transcribe.py after Coco reviews this checkpoint | Needs: Coco to run `python -m callguard.audio.capture --rms` on the Mac during a call and confirm caller/you RMS routing; pin sounddevice==0.5.6, numpy==2.3.5, faster-whisper==1.2.1 in requirements.txt and pre-download Whisper small
