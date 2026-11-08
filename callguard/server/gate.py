"""SRV-9: a timed warning state, never an OS keyboard or mouse lock."""
from __future__ import annotations

import asyncio
import math
import os
import time
from typing import Any, Callable

from callguard.server.callrisk import asks
from callguard.shared.contracts import Gate, ScamCheck

LOCK_CONFIDENCE = 0.85
RELEASE_SECONDS = 120
RELEASE_WAYS = frozenset({"hang_up", "colleague", "mark_safe"})
ARMED_REASON = "Verify this call before you act."
LOCKED_REASON = "Pause before sharing money, access, or personal information. Verify the caller first."


def gate_enabled() -> bool:
    # Off by default (Coco, Sat: the pause was removed from the product). CALLGUARD_GATE=on brings it back.
    return os.environ.get("CALLGUARD_GATE", "off").strip().lower() == "on"


class SoftGate:
    """Off → armed → locked → released, with wire state off for released."""

    def __init__(self, broadcast: Callable[..., Any], *, timeout: float = RELEASE_SECONDS,
                 enabled: Callable[[], bool] = gate_enabled) -> None:
        self.broadcast = broadcast
        self.timeout = timeout
        self.enabled = enabled
        self.state = "off"  # "released" is internal; not part of the UI contract
        self.seen_asks: set[str] = set()
        self.deadline: float | None = None
        self._timer: asyncio.Task | None = None

    def snapshot(self) -> Gate:
        remaining = max(0, math.ceil(self.deadline - time.monotonic())) if self.deadline else 0
        state = self.state if self.state in {"armed", "locked"} else "off"
        reason = LOCKED_REASON if state == "locked" else ARMED_REASON if state == "armed" else ""
        return {"state": state, "reason": reason, "release_in": remaining}

    async def _push(self) -> None:
        await self.broadcast("gate", self.snapshot())

    def _cancel_timer(self) -> None:
        if self._timer and self._timer is not asyncio.current_task():
            self._timer.cancel()
        self._timer = None
        self.deadline = None

    async def _timeout(self, deadline: float) -> None:
        try:
            await asyncio.sleep(self.timeout)
            if self.state == "locked" and self.deadline == deadline:
                await self.release("timeout")
        except asyncio.CancelledError:
            pass

    async def on_check(self, raw: ScamCheck, shown: ScamCheck) -> None:
        if not self.enabled():
            if self.state != "off":
                await self.reset()
            return
        if shown.get("risk") != "danger":
            return
        confidence = raw.get("confidence")
        qualified = (asks(raw) if isinstance(confidence, (int, float))
                     and confidence >= LOCK_CONFIDENCE else set())
        new_asks = qualified - self.seen_asks
        self.seen_asks |= qualified
        if self.state == "off" and not qualified:
            self.state = "armed"
            await self._push()
            return
        if not qualified or self.state == "locked":
            return
        if self.state == "released" and not new_asks:
            return
        self.state = "locked"
        self.deadline = asyncio.get_running_loop().time() + self.timeout
        self._timer = asyncio.create_task(self._timeout(self.deadline))
        await self._push()

    async def release(self, how: str) -> bool:
        """Release the overlay. Timeout is internal; UI ways are allowlisted."""
        if how not in RELEASE_WAYS | {"timeout"} or self.state not in {"locked", "armed"}:
            return False
        self._cancel_timer()
        self.state = "released"
        await self._push()
        return True

    async def reset(self) -> None:
        previous = self.state
        self._cancel_timer()
        self.state = "off"
        self.seen_asks.clear()
        if previous in {"armed", "locked"}:
            await self._push()

    def close(self) -> None:
        """Forget gate state as the app stops; the event loop owns task cleanup."""
        self.state = "off"
        self.seen_asks.clear()
        self.deadline = None
