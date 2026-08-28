"""In-process invalidation bus.

pyee fans out the wake-up; ``_revs`` is why a busy subscriber sees one
jump rather than a queue. Single-process only — multiple uvicorn workers
would split ingest and the stream across processes.
"""
from __future__ import annotations

import asyncio

from pyee import EventEmitter

from ...domain.interfaces.bus import IRunEventBus


class InMemoryRunEventBus(IRunEventBus):
    def __init__(self) -> None:
        self._ee = EventEmitter()
        self._revs: dict[str, int] = {}

    async def publish(self, run_id: str) -> None:
        self._revs[run_id] = self._revs.get(run_id, 0) + 1
        self._ee.emit(run_id)

    async def wait(self, run_id: str, since_rev: int) -> int:
        if (rev := self._revs.get(run_id, 0)) > since_rev:
            return rev

        woke = asyncio.Event()

        def on_event() -> None:
            woke.set()

        self._ee.on(run_id, on_event)
        try:
            await woke.wait()
        finally:
            self._ee.remove_listener(run_id, on_event)
        return self._revs[run_id]

    def current_rev(self, run_id: str) -> int:
        return self._revs.get(run_id, 0)


_bus: InMemoryRunEventBus | None = None


def get_run_event_bus() -> InMemoryRunEventBus:
    """Process-wide singleton so ingest and the stream share one bus."""
    global _bus
    if _bus is None:
        _bus = InMemoryRunEventBus()
    return _bus


def reset_run_event_bus() -> None:
    """Drop the singleton. For test isolation only."""
    global _bus
    _bus = None
