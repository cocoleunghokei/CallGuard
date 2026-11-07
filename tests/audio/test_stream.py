from callguard.audio import stream_chunks
from callguard.audio.capture import AudioChunk


def test_stream_chunks_combines_both_speakers_and_skips_empty_text(monkeypatch):
    warmed = []
    closed = []
    caller = object()
    silence = object()
    you = object()

    def fake_capture():
        try:
            yield AudioChunk("caller", caller, 0.0, 3.0)
            yield AudioChunk("caller", silence, 3.0, 6.0)
            yield AudioChunk("you", you, 3.0, 6.0)
        finally:
            closed.append(True)

    monkeypatch.setattr("callguard.audio.stream.get_model", lambda: warmed.append(True))
    monkeypatch.setattr("callguard.audio.stream.capture_chunks", fake_capture)
    monkeypatch.setattr(
        "callguard.audio.stream.transcribe_chunk",
        lambda samples: {caller: "Hello", silence: "", you: "I hear you"}[samples],
    )

    assert list(stream_chunks()) == [
        {"speaker": "caller", "text": "Hello", "start": 0.0, "end": 3.0, "language": "en"},
        {"speaker": "you", "text": "I hear you", "start": 3.0, "end": 6.0, "language": "en"},
    ]
    assert warmed == [True]
    assert closed == [True]


def test_closing_stream_stops_capture(monkeypatch):
    closed = []

    def fake_capture():
        try:
            yield AudioChunk("caller", object(), 0.0, 3.0)
            yield AudioChunk("caller", object(), 3.0, 6.0)
        finally:
            closed.append(True)

    monkeypatch.setattr("callguard.audio.stream.get_model", lambda: None)
    monkeypatch.setattr("callguard.audio.stream.capture_chunks", fake_capture)
    monkeypatch.setattr("callguard.audio.stream.transcribe_chunk", lambda samples: "words")

    stream = stream_chunks()
    assert next(stream)["speaker"] == "caller"
    stream.close()
    assert closed == [True]
