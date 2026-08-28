"""Tests for the in-process invalidation bus.

The bus's whole value is that coalescing and backpressure-immunity fall out
of its shape rather than being configured, so those are what these tests
pin down. See docs/decisions/0001-invalidation-bus-over-event-stream.md.
"""
import asyncio

import pytest

from agent_trace.infrastructure.bus import (
    InMemoryRunEventBus,
    get_run_event_bus,
    reset_run_event_bus,
)


class TestRevisions:
    """Revision counter semantics."""

    def test_unknown_run_starts_at_zero(self) -> None:
        bus = InMemoryRunEventBus()

        assert bus.current_rev("never-seen") == 0

    @pytest.mark.asyncio
    async def test_publish_increments(self) -> None:
        bus = InMemoryRunEventBus()

        await bus.publish("run-1")
        await bus.publish("run-1")

        assert bus.current_rev("run-1") == 2

    @pytest.mark.asyncio
    async def test_runs_are_independent(self) -> None:
        bus = InMemoryRunEventBus()

        await bus.publish("run-1")

        assert bus.current_rev("run-1") == 1
        assert bus.current_rev("run-2") == 0


class TestWait:
    """Blocking and wake-up behaviour."""

    @pytest.mark.asyncio
    async def test_returns_immediately_when_already_behind(self) -> None:
        """A caller that missed a publish must not block waiting for another."""
        bus = InMemoryRunEventBus()
        await bus.publish("run-1")

        rev = await asyncio.wait_for(bus.wait("run-1", since_rev=0), timeout=1)

        assert rev == 1

    @pytest.mark.asyncio
    async def test_blocks_until_published(self) -> None:
        bus = InMemoryRunEventBus()
        waiter = asyncio.create_task(bus.wait("run-1", since_rev=0))
        await asyncio.sleep(0)

        assert not waiter.done()

        await bus.publish("run-1")

        assert await asyncio.wait_for(waiter, timeout=1) == 1

    @pytest.mark.asyncio
    async def test_ignores_other_runs(self) -> None:
        bus = InMemoryRunEventBus()
        waiter = asyncio.create_task(bus.wait("run-1", since_rev=0))
        await asyncio.sleep(0)

        await bus.publish("run-2")
        await asyncio.sleep(0)

        assert not waiter.done()
        waiter.cancel()

    @pytest.mark.asyncio
    async def test_all_waiters_wake(self) -> None:
        """Two browsers on the same run must both be woken by one publish."""
        bus = InMemoryRunEventBus()
        waiters = [asyncio.create_task(bus.wait("run-1", since_rev=0)) for _ in range(3)]
        await asyncio.sleep(0)

        await bus.publish("run-1")

        results = await asyncio.wait_for(asyncio.gather(*waiters), timeout=1)
        assert results == [1, 1, 1]

    @pytest.mark.asyncio
    async def test_publishes_coalesce(self) -> None:
        """N publishes while a subscriber is busy produce one wake, not N.

        This is the property that makes backpressure impossible: a slow
        client observes a single larger jump in rev rather than a backlog.
        """
        bus = InMemoryRunEventBus()
        wakes = 0

        async def subscriber() -> None:
            nonlocal wakes
            rev = 0
            while rev < 20:
                rev = await bus.wait("run-1", rev)
                wakes += 1
                # Stand in for the refetch a real subscriber would do.
                await asyncio.sleep(0.02)

        task = asyncio.create_task(subscriber())
        await asyncio.sleep(0)

        for _ in range(20):
            await bus.publish("run-1")

        await asyncio.wait_for(task, timeout=2)

        assert bus.current_rev("run-1") == 20
        # One wake for the burst, at most one more to observe the final rev.
        assert wakes <= 2

    @pytest.mark.asyncio
    async def test_no_lost_wakeup_between_waits(self) -> None:
        """A publish landing between two waits must not be missed."""
        bus = InMemoryRunEventBus()

        rev = await asyncio.wait_for(
            asyncio.gather(
                bus.wait("run-1", since_rev=0),
                _publish_soon(bus, "run-1"),
            ),
            timeout=1,
        )
        assert rev[0] == 1

        await bus.publish("run-1")  # lands while nobody is waiting

        assert await asyncio.wait_for(bus.wait("run-1", since_rev=1), timeout=1) == 2


async def _publish_soon(bus: InMemoryRunEventBus, run_id: str) -> None:
    await asyncio.sleep(0)
    await bus.publish(run_id)


class TestSingleton:
    """The bus must be shared across requests, or fan-out silently fails."""

    def test_get_returns_same_instance(self) -> None:
        reset_run_event_bus()
        try:
            assert get_run_event_bus() is get_run_event_bus()
        finally:
            reset_run_event_bus()

    def test_reset_replaces_instance(self) -> None:
        reset_run_event_bus()
        first = get_run_event_bus()
        reset_run_event_bus()

        assert get_run_event_bus() is not first
        reset_run_event_bus()
