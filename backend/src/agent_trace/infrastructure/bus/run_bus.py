"""In-process invalidation bus.

Not a queue. It holds a per-run revision counter and a swappable
``asyncio.Event``, and nothing else -- no events, no payloads, no
per-subscriber state. See
`docs/decisions/0001-invalidation-bus-over-event-stream.md`.

Single-process only. Running the backend with multiple uvicorn workers
would silently break fan-out: ingest lands on one worker, the stream on
another, and the stream never wakes.
"""
from __future__ import annotations

import asyncio

from ...domain.interfaces.bus import IRunEventBus


class InMemoryRunEventBus(IRunEventBus):
    """Revision-counter bus backed by ``asyncio.Event``.

    Coalescing is inherent rather than configured: waiters re-read the
    revision instead of draining a queue, so N publishes arriving while a
    subscriber is busy result in exactly one wake-up and one larger jump
    in ``rev``. Backpressure therefore cannot occur.

    Example:
        >>> bus = InMemoryRunEventBus()
        >>> await bus.publish("run-1")
        >>> await bus.wait("run-1", since_rev=0)
        1
    """

    def __init__(self) -> None:
        self._revs: dict[str, int] = {}
        self._events: dict[str, asyncio.Event] = {}

    async def publish(self, run_id: str) -> None:
        """Bump the run's revision and wake every current waiter.

        Pop-and-set rather than set-and-clear: popping hands the event to
        the waiters that are already blocked on it, while the next call to
        `wait` installs a fresh one. That avoids the lost-wakeup race a
        shared, re-cleared event would have.

        Async so Starlette runs it on the event loop rather than in a
        threadpool -- see IRunEventBus.publish.
        """
        self._revs[run_id] = self._revs.get(run_id, 0) + 1
        event = self._events.pop(run_id, None)
        if event is not None:
            event.set()

    async def wait(self, run_id: str, since_rev: int) -> int:
        """Block until this run's revision exceeds ``since_rev``."""
        while True:
            rev = self._revs.get(run_id, 0)
            if rev > since_rev:
                return rev
            event = self._events.get(run_id)
            if event is None:
                event = asyncio.Event()
                self._events[run_id] = event
            await event.wait()

    def current_rev(self, run_id: str) -> int:
        """Current revision for a run; 0 if never published to."""
        return self._revs.get(run_id, 0)


# Module-global singleton, matching the pattern used for the database
# connection in infrastructure/database/connection.py. The bus must be
# shared across requests -- constructing it per-request via Depends would
# mean ingest and the stream never see each other.
_bus: InMemoryRunEventBus | None = None


def get_run_event_bus() -> InMemoryRunEventBus:
    """Return the process-wide bus, creating it on first use."""
    global _bus
    if _bus is None:
        _bus = InMemoryRunEventBus()
    return _bus


def reset_run_event_bus() -> None:
    """Drop the process-wide bus. For test isolation only."""
    global _bus
    _bus = None
