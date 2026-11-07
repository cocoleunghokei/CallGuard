"""Shared contracts between lanes. Owned by Coco (Lead). Agents never edit this file.

Change rules (root AGENTS.md, guardrail 7): adding an optional field is fine;
never rename or remove one. Update AGENTS.md section 3 in the same commit.

v2 (hack1984/prd.md section 12): every addition is optional (NotRequired),
so code written against v1 keeps working.
"""
from typing import Literal, NotRequired, Optional, TypedDict

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
    # v2
    "payment_request",
    "remote_access",
    "personal_data_request",
    "inside_knowledge",
]
TACTICS: tuple[str, ...] = Tactic.__args__  # type: ignore[attr-defined]

SafeSignal = Literal[
    "callback_known_number",
    "follows_normal_approval",
    "no_money_or_data_asked",
    "asks_in_writing",
]
SAFE_SIGNALS: tuple[str, ...] = SafeSignal.__args__  # type: ignore[attr-defined]


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
    # v2
    keywords: NotRequired[list[str]]  # phrases that also trigger the rule
    requires: NotRequired[list[str]]  # tactics that must also be present
    enabled: NotRequired[bool]  # default True; disabled rules never match (UI-14)


class Evidence(TypedDict):
    tactic: str
    quote: str  # <= 80 chars, verbatim from the window
    strength: Literal["clear", "hint", "phrase"]
    speaker: Speaker


class ScamCheck(TypedDict):
    risk: Risk
    tactics: list[str]
    claimed_identity: Optional[str]
    rules_broken: list[str]
    reason: str
    next_step: str
    # v2
    confidence: NotRequired[float]  # 0-1
    evidence: NotRequired[list[Evidence]]
    safe_signals: NotRequired[list[str]]
    source: NotRequired[Literal["model", "fast", "fallback"]]


class EgressEntry(TypedDict):
    time: str  # ISO 8601, local time
    destination: str  # host only, e.g. "api.tavily.com"
    sent: str  # exactly what left the device (the full query); "" when refused
    # "refused": the query failed egress.safe_org(), nothing was sent (v2)
    status: Literal["ok", "offline", "error", "refused"]


class ScamReport(TypedDict):
    summary: str  # <= 120 chars, from the search result, never model-generated
    source_url: str
    date: str  # "YYYY-MM"


class Verify(TypedDict):
    org: str
    phone: NotRequired[str]
    source_url: NotRequired[str]
    status: NotRequired[Literal["ok", "offline", "not_found", "error"]]
    report: NotRequired[ScamReport]  # P1 (C17), omitted when nothing recent


class Status(TypedDict):
    listening: bool
    online: bool
    model: NotRequired[Literal["ok", "degraded", "offline"]]
    gate: NotRequired[Literal["off", "on"]]


class Gate(TypedDict):
    state: Literal["off", "armed", "locked"]
    reason: str
    release_in: int  # seconds until the overlay steps back on its own


class Call(TypedDict):
    state: Literal["started", "ended"]


class RulesSaved(TypedDict):
    ok: bool
    errors: NotRequired[list[str]]


# WebSocket message: {"type": MessageType, "data": ...}
# data per type: transcript=TranscriptChunk, check=ScamCheck, verify=Verify,
# egress=EgressEntry, status=Status, gate=Gate, call=Call,
# rules=list[Rule] (optional top-level "source": "default" | "custom"),
# rules_saved=RulesSaved
MessageType = Literal[
    "transcript", "check", "verify", "egress", "status",
    # v2
    "gate", "call", "rules", "rules_saved",
]

# UI -> Server: {"type": ClientMessageType, ...}
# gate_release carries "how": "hang_up" | "colleague" | "mark_safe";
# save_rules carries "data": list[Rule]
ClientMessageType = Literal[
    "colleague", "mark_safe",
    # v2
    "gate_release", "end_call", "save_rules", "reset_rules",
]
