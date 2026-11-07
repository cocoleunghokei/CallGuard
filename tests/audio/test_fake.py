from pathlib import Path

import pytest

from callguard.audio import fake_stream


FIXTURES = Path(__file__).parent / "fixtures"


def test_fake_stream_parses_headers_speakers_and_call_timestamps():
    chunks = list(fake_stream(FIXTURES / "two_speakers.txt", speed=0))

    assert chunks == [
        {"speaker": "caller", "text": "Hello, this is the vendor.", "start": 0.0, "end": 3.0, "language": "en"},
        {"speaker": "you", "text": "Could you email the invoice?", "start": 3.0, "end": 6.0, "language": "en"},
        {"speaker": "caller", "text": "Please use the new account number.", "start": 6.0, "end": 9.0, "language": "en"},
    ]
    assert len(list(fake_stream(FIXTURES / "one_caller.txt", speed=0))) == 1


def test_fake_stream_scales_replay_delay_without_changing_timestamps(monkeypatch):
    now = 0.0
    delays = []

    def advance(seconds):
        nonlocal now
        delays.append(seconds)
        now += seconds

    monkeypatch.setattr("callguard.audio.fake.monotonic", lambda: now)
    monkeypatch.setattr("callguard.audio.fake.sleep", advance)

    chunks = list(fake_stream(FIXTURES / "two_speakers.txt", speed=2))
    assert delays == [1.5, 1.5, 1.5]
    assert [chunk["end"] for chunk in chunks] == [3.0, 6.0, 9.0]


@pytest.mark.parametrize("speed", [-1, float("inf"), float("nan")])
def test_fake_stream_rejects_invalid_speed(speed):
    with pytest.raises(ValueError, match="speed"):
        list(fake_stream(FIXTURES / "one_caller.txt", speed=speed))


def test_every_detection_scenario_replays_without_delay():
    scripts = sorted((Path(__file__).parents[1] / "detection" / "scripts").glob("*.txt"))
    assert len(scripts) >= 8

    for script in scripts:
        utterances = [
            line for line in script.read_text(encoding="utf-8").splitlines()
            if line.startswith(("caller:", "you:"))
        ]
        chunks = list(fake_stream(script, speed=0))
        assert len(chunks) == len(utterances), script.name
        assert [chunk["start"] for chunk in chunks] == [3.0 * i for i in range(len(chunks))]
        assert all(chunk["language"] == "en" for chunk in chunks)
