"""Shared contracts between lanes. Owned by Coco (Lead). Agents never edit this file.

Change rules (root AGENTS.md, guardrail 7): adding an optional field is fine;
never rename or remove one. Update AGENTS.md section 3 in the same commit.
"""
from typing import Literal, Optional, TypedDict

Speaker = Literal["caller", "you"]
Risk = Literal["low", "watch", "danger"]
Tactic = Literal[
    "authority",
    "secrecy",
    "urgency",
    "threat",
    "credential_request",
    "bank_change",
    "bypass_approval",
]
TACTICS: tuple[str, ...] = Tactic.__args__  # type: ignore[attr-defined]


class TranscriptChunk(TypedDict):
    speaker: Speaker
    text: str
    start: float  # seconds since the call started
    end: float
    language: str  # "en", "zh", ...


class Rule(TypedDict):
    id: str
    text: str
    tactics: list[str]  # tactics that trigger this rule


class ScamCheck(TypedDict):
    risk: Risk
    tactics: list[str]
    claimed_identity: Optional[str]
    rules_broken: list[str]
    reason: str
    next_step: str


class EgressEntry(TypedDict):
    time: str  # ISO 8601, local time
    destination: str  # host only, e.g. "api.tavily.com"
    sent: str  # exactly what left the device
    status: Literal["ok", "offline", "error"]


# WebSocket message: {"type": MessageType, "data": ...}
MessageType = Literal["transcript", "check", "verify", "egress", "status"]
ClientMessageType = Literal["colleague", "mark_safe"]
