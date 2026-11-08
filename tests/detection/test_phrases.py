"""DET-11: the urgency phrase spotter is generic, caller-only and verbatim."""
import pytest

from callguard.detection.phrases import phrase_evidence


@pytest.mark.parametrize("line", [
    "Do it right now please.",
    "I need this done immediately.",
    "Send it as soon as possible.",
    "Can you change it now while we're talking?",
    "It has to go in the next ten minutes.",
    "I've only got a minute here.",
    "Get it out before 3pm.",
    "Have it done by end of day.",
    "Make the transfer before noon.",
])
def test_time_pressure_is_spotted(line):
    (item,) = phrase_evidence([("caller", line)])
    assert item["tactic"] == "urgency" and item["strength"] == "phrase"
    assert item["speaker"] == "caller" and item["quote"] in line


@pytest.mark.parametrize("line", [
    "Hi, it's Priya. Did you get my email about Friday?",
    "See you Friday at four.",
    "We saw a charge at an electronics store yesterday.",
    "Line 3 on invoice 2210 has the wrong quantity.",
    "Now, about the invoice you sent.",
    "I'll call you back by Tuesday.",
    "Pass it by two-step verification first.",
])
def test_ordinary_lines_are_not_urgency(line):
    assert phrase_evidence([("caller", line)]) == []


def test_only_caller_lines_count():
    assert phrase_evidence([("you", "I'll do it right now.")]) == []
