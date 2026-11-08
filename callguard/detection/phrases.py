"""DET-11: instant, deterministic urgency spotter (strength "phrase", prd §6).

The live eval showed the model reliably drops `urgency` when the time pressure
sits inside the same sentence as the main ask ("update it now while I'm on the
line"), which keeps S2/S3/S4 just under danger. This spotter adds `phrase`
evidence for clear time-pressure wording in CALLER lines only.

Safety: score.py's G3 caps phrase-only evidence below danger, and G1 caps
urgency on its own, so this can only help when the model also found a real ask.
Patterns stay generic (no script-specific words) to limit overfitting the eval.
"""
from __future__ import annotations

import re

from callguard.shared.contracts import Evidence

from .parse import MAX_QUOTE, Line

_NUM = r"(?:\d+|a|an|one|two|three|four|five|ten|fifteen|twenty|thirty|a few|a couple of)"
_CLOCK = (r"(?:noon|midday|lunch|close of business|(?:the )?end of (?:the )?day|tonight|"
          r"\d{1,2}(?::\d{2})?\s?(?:am|pm)?|one|two|three|four|five|six|seven|eight|nine|"
          r"ten|eleven|twelve)(?:\s?o'clock)?")
URGENCY = re.compile("|".join((
    r"\bright (?:now|away)\b",
    r"\bimmediately\b",
    r"\b(?:asap|as soon as possible|as fast as you can)\b",
    r"\b(?:quickly|hurry|urgent(?:ly)?)\b",
    r"\b(?:now,? )?while (?:i'm|i am|we're|we are) (?:still )?(?:on the (?:line|phone|call)|talking)\b",
    rf"\bin the next {_NUM} (?:minutes?|hours?)\b",
    rf"\b(?:i've|i have|i) (?:only )?(?:got|have) (?:only )?{_NUM} (?:minutes?|seconds?|moment)\b",
    rf"\b(?:before|by) {_CLOCK}(?![\w-])",
)), re.I)


def phrase_evidence(lines: list[Line]) -> list[Evidence]:
    """Return at most one `urgency` phrase item, quoting the caller's own words."""
    for speaker, text in lines:
        if speaker != "caller":
            continue
        m = URGENCY.search(text.replace("’", "'"))
        if m:
            return [{"tactic": "urgency", "quote": text[m.start(): m.end()][:MAX_QUOTE],
                     "strength": "phrase", "speaker": "caller"}]
    return []
