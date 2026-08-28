"""Port for the run invalidation bus.

The bus carries *the fact that a run changed*, never the change itself. See
`docs/decisions/0001-invalidation-bus-over-event-stream.md` for why.
"""
from __future__ import annotations

from abc import ABC, abstractmethod


class IRunEventBus(ABC):
    """Abstract fan-out between ingest and connected stream subscribers.

    Keyed by ``run_id`` because that is the only identifier the ingest path
    has. Record-scoped streams resolve their run once and wait on it.
    """

    @abstractmethod
    async def publish(self, run_id: str) -> None:
        """Mark a run as changed and wake every waiter on it.

        Must be called only after the ingest transaction has committed --
        a waiter that wakes early will refetch stale data and then never be
        told again.

        Async even though the work is trivial: the implementation wakes
        waiters via asyncio primitives, which are not thread-safe.
        Starlette runs a *sync* background task in a threadpool, so a
        sync ``publish`` could silently fail to wake waiters.

        Args:
            run_id: The run whose stored data just changed.
        """
        ...

    @abstractmethod
    async def wait(self, run_id: str, since_rev: int) -> int:
        """Block until the run's revision exceeds ``since_rev``.

        Returns immediately if it already does, which is what makes
        coalescing free: a subscriber that was busy fetching observes one
        larger jump rather than a backlog.

        Args:
            run_id: The run to watch.
            since_rev: The revision the caller has already handled.

        Returns:
            The current revision, always greater than ``since_rev``.
        """
        ...

    @abstractmethod
    def current_rev(self, run_id: str) -> int:
        """Current revision for a run; 0 if it has never been published to."""
        ...
