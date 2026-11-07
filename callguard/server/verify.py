"""SRV-8 (C12): verify the claimed organization once per org per call.

Trigger: a check with claimed_identity set and confidence >= 0.40 (or, when a
check has no confidence, risk watch or danger). Before anything is sent,
egress.safe_org() must pass against the CALLER's lines in the current window
and the never-search list; otherwise the egress log gets a `refused` entry and
nothing leaves the device. The search runs in a thread, so checks keep flowing.

UI messages: `verify {org}` first (= "Looking up…"), then
`verify {org, status, phone?, source_url?}`.
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any, Callable

from callguard.server import egress
from callguard.shared.contracts import ScamCheck

log = logging.getLogger("callguard.server.verify")

MIN_CONFIDENCE = 0.40


def wants_verify(check: ScamCheck) -> bool:
    if not check.get("claimed_identity"):
        return False
    conf = check.get("confidence")
    if isinstance(conf, (int, float)):
        return conf >= MIN_CONFIDENCE
    return check.get("risk") in ("watch", "danger")


class Verifier:
    def __init__(self, broadcast: Callable[..., Any], caller_lines: Callable[[], list[str]],
                 call_id: Callable[[], int]) -> None:
        self.broadcast = broadcast
        self.caller_lines = caller_lines
        self.call_id = call_id
        self.cache: dict[str, dict] = {}  # normalized org -> verify (this call only)
        self.tasks: set[asyncio.Task] = set()

    def reset(self) -> None:
        self.cache.clear()

    async def __call__(self, raw: ScamCheck, shown: ScamCheck) -> None:
        check = raw if wants_verify(raw) else shown
        if not wants_verify(check):
            return
        org = " ".join(str(check["claimed_identity"]).split())
        key = org.lower()
        if key in self.cache:
            return
        self.cache[key] = {"org": org}
        refusal = egress.org_refusal(org, self.caller_lines(), egress.never_search_from_env())
        if refusal:
            log.info("verify refused: %s", refusal)  # the reason never contains the name
            egress.record_refused()
            self.cache[key] = {"org": org, "status": "error"}
            await self.broadcast("verify", self.cache[key])
            return
        await self.broadcast("verify", {"org": org})  # "Looking up…"
        task = asyncio.get_running_loop().create_task(self._lookup(org, key, self.call_id(), self.caller_lines()))
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def _lookup(self, org: str, key: str, call_id: int, caller_lines: list[str]) -> None:
        if call_id != self.call_id():
            return
        result = await asyncio.to_thread(egress.search, org, caller_lines)
        if call_id != self.call_id():
            return  # the call ended meanwhile
        self.cache[key] = dict(result)
        await self.broadcast("verify", result)

    async def drain(self) -> None:
        while self.tasks:
            await asyncio.gather(*list(self.tasks), return_exceptions=True)
