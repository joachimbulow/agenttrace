"""Integration tests for the record projection and the live invalidation stream.

These deliberately do *not* use the shared `client` fixture. That fixture
overrides the session dependency with one long-lived session that is never
committed, which is exactly the behaviour the publish-after-commit test
needs to observe for real. So this module wires up a genuine `Database`
via `init_db` and lets FastAPI's dependency teardown do the committing.
"""
from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
import pytest_asyncio
from fastapi import BackgroundTasks
from httpx import ASGITransport, AsyncClient

from agent_trace.application.dto import IngestRequest, IngestResponse
from agent_trace.infrastructure import database as database_module
from agent_trace.infrastructure.bus import (
    InMemoryRunEventBus,
    get_run_event_bus,
    reset_run_event_bus,
)
from agent_trace.infrastructure.database import get_db, init_db
from agent_trace.main import app
from agent_trace.presentation.routers import ingest as ingest_router
from agent_trace.presentation.routers import records as records_router

BASE = datetime(2026, 8, 28, 12, 0, 0, tzinfo=UTC)


def _at(seconds: float) -> str:
    return (BASE + timedelta(seconds=seconds)).isoformat()


@pytest_asyncio.fixture
async def live_client() -> AsyncIterator[AsyncClient]:
    """Client backed by a real Database, with real commit boundaries."""
    app.dependency_overrides.clear()
    reset_run_event_bus()
    await init_db("sqlite+aiosqlite:///:memory:")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await get_db().engine.dispose()
    database_module.connection._db = None
    reset_run_event_bus()


def _span_start(
    span_id: str,
    name: str,
    *,
    parent_id: str | None = None,
    span_type: str = "step",
    at: float = 0.0,
    attributes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "type": "span_start",
        "data": {
            "span_id": span_id,
            "parent_id": parent_id,
            "name": name,
            "span_type": span_type,
            "timestamp": _at(at),
            "attributes": attributes or {},
        },
    }


def _span_end(span_id: str, at: float) -> dict[str, Any]:
    return {"type": "span_end", "data": {"span_id": span_id, "timestamp": _at(at)}}


def _span_event(span_id: str, event_type: str, at: float) -> dict[str, Any]:
    return {
        "type": "span_event",
        "data": {
            "span_id": span_id,
            "event_type": event_type,
            "timestamp": _at(at),
            "payload": {"value": "x"},
        },
    }


async def _ingest(client: AsyncClient, run_id: str, events: list[dict[str, Any]]) -> None:
    response = await client.post(
        "/api/v1/ingest/events",
        json={"run_id": run_id, "run_name": "primo_cleanup_pipeline", "events": events},
    )
    assert response.status_code == 202, response.text


async def _seed_two_records(client: AsyncClient, run_id: str = "run-1") -> str:
    """A pipeline root with two records, one finished and one running."""
    await _ingest(
        client,
        run_id,
        [
            _span_start("root", "primo_cleanup_pipeline", span_type="agent_run", at=0),
            _span_start(
                "record-a",
                "primo_record[REC-1]",
                parent_id="root",
                span_type="agent_run",
                at=1,
                attributes={"record_id": "REC-1", "policy_id": "POL-1001"},
            ),
            _span_start("a-gate", "gate", parent_id="record-a", at=2),
            _span_end("a-gate", at=3),
            _span_end("record-a", at=4),
            _span_start(
                "record-b",
                "primo_record[REC-2]",
                parent_id="root",
                span_type="agent_run",
                at=1.5,
                attributes={"record_id": "REC-2", "policy_id": "POL-1002"},
            ),
            _span_start("b-gate", "gate", parent_id="record-b", at=2.5),
        ],
    )
    return run_id


class TestRecordList:
    """GET /api/v1/records?run_id=..."""

    @pytest.mark.asyncio
    async def test_unknown_run_is_404(self, live_client: AsyncClient) -> None:
        response = await live_client.get("/api/v1/records", params={"run_id": "nope"})

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_run_id_is_required(self, live_client: AsyncClient) -> None:
        response = await live_client.get("/api/v1/records")

        assert response.status_code == 422

    @pytest.mark.asyncio
    async def test_lists_records_not_the_run_root(
        self, live_client: AsyncClient
    ) -> None:
        """The pipeline root is a container, not a record."""
        run_id = await _seed_two_records(live_client)

        data = (await live_client.get("/api/v1/records", params={"run_id": run_id})).json()

        assert [r["id"] for r in data["records"]] == ["record-a", "record-b"]
        assert [r["record_id"] for r in data["records"]] == ["REC-1", "REC-2"]
        assert data["records"][0]["policy_id"] == "POL-1001"

    @pytest.mark.asyncio
    async def test_status_and_counts_are_derived(self, live_client: AsyncClient) -> None:
        run_id = await _seed_two_records(live_client)

        records = (
            await live_client.get("/api/v1/records", params={"run_id": run_id})
        ).json()["records"]
        by_id = {r["id"]: r for r in records}

        assert by_id["record-a"]["status"] == "completed"
        assert by_id["record-a"]["duration_ms"] == 3000.0
        assert by_id["record-a"]["node_count"] == 2
        assert by_id["record-b"]["status"] == "running"
        assert by_id["record-b"]["ended_at"] is None

    @pytest.mark.asyncio
    async def test_error_event_beats_completion(self, live_client: AsyncClient) -> None:
        """A record whose root closed but which contains a failure is an error."""
        run_id = await _seed_two_records(live_client)
        await _ingest(live_client, run_id, [_span_event("a-gate", "error", at=3)])

        records = (
            await live_client.get("/api/v1/records", params={"run_id": run_id})
        ).json()["records"]

        assert next(r for r in records if r["id"] == "record-a")["status"] == "error"

    @pytest.mark.asyncio
    async def test_falls_back_to_root_children_without_record_ids(
        self, live_client: AsyncClient
    ) -> None:
        """A program traced with the bare SDK still gets records, not an empty list."""
        await _ingest(
            live_client,
            "run-plain",
            [
                _span_start("r", "my_agent", span_type="agent_run", at=0),
                _span_start("s1", "step-one", parent_id="r", at=1),
                _span_start("s2", "step-two", parent_id="r", at=2),
            ],
        )

        records = (
            await live_client.get("/api/v1/records", params={"run_id": "run-plain"})
        ).json()["records"]

        assert [r["id"] for r in records] == ["s1", "s2"]
        assert records[0]["record_id"] is None

    @pytest.mark.asyncio
    async def test_single_span_run_is_its_own_record(self, live_client: AsyncClient) -> None:
        await _ingest(
            live_client,
            "run-solo",
            [_span_start("only", "my_agent", span_type="agent_run", at=0)],
        )

        records = (
            await live_client.get("/api/v1/records", params={"run_id": "run-solo"})
        ).json()["records"]

        assert [r["id"] for r in records] == ["only"]


class TestRecordTree:
    """GET /api/v1/records/{record_id}"""

    @pytest.mark.asyncio
    async def test_unknown_record_is_404(self, live_client: AsyncClient) -> None:
        response = await live_client.get("/api/v1/records/nope")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_only_that_records_subtree(self, live_client: AsyncClient) -> None:
        """Sibling records must not leak into the canvas."""
        await _seed_two_records(live_client)

        data = (await live_client.get("/api/v1/records/record-a")).json()

        assert data["id"] == "record-a"
        assert data["run_id"] == "run-1"
        assert data["root"]["id"] == "record-a"
        assert [c["id"] for c in data["root"]["children"]] == ["a-gate"]

    @pytest.mark.asyncio
    async def test_carries_event_payloads_inline(self, live_client: AsyncClient) -> None:
        """Card detail and error status both need events in the same payload."""
        await _seed_two_records(live_client)
        await _ingest(live_client, "run-1", [_span_event("a-gate", "output", at=3)])

        data = (await live_client.get("/api/v1/records/record-a")).json()

        gate = data["root"]["children"][0]
        assert [e["event_type"] for e in gate["events"]] == ["output"]
        assert gate["events"][0]["payload"] == {"value": "x"}

    @pytest.mark.asyncio
    async def test_children_ordered_by_start_time(self, live_client: AsyncClient) -> None:
        """Layout must be stable between ticks, so ordering cannot be arbitrary."""
        await _ingest(
            live_client,
            "run-order",
            [
                _span_start(
                    "record",
                    "record",
                    span_type="agent_run",
                    at=0,
                    attributes={"record_id": "R"},
                ),
                _span_start("late", "late", parent_id="record", at=9),
                _span_start("early", "early", parent_id="record", at=1),
                _span_start("mid", "mid", parent_id="record", at=5),
            ],
        )

        data = (await live_client.get("/api/v1/records/record")).json()

        assert [c["id"] for c in data["root"]["children"]] == ["early", "mid", "late"]


class _StubRequest:
    """Stand-in for Request, which the stream only uses to detect hangup."""

    def __init__(self) -> None:
        self.disconnected = False

    async def is_disconnected(self) -> bool:
        return self.disconnected


class TestRecordStreamRoute:
    """GET /api/v1/records/{record_id}/events -- the route around the generator.

    The stream itself is exercised in TestPingStream: httpx's ASGI
    transport buffers the whole response body, so it can never return from
    a stream that by design never ends.
    """

    @pytest.mark.asyncio
    async def test_unknown_record_is_404(self, live_client: AsyncClient) -> None:
        response = await live_client.get("/api/v1/records/nope/events")

        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_sets_streaming_headers(self, live_client: AsyncClient) -> None:
        await _seed_two_records(live_client)

        response = await records_router.stream_record_events(
            record_id="record-a",
            request=_StubRequest(),  # type: ignore[arg-type]
            bus=get_run_event_bus(),
        )

        assert response.media_type == "text/event-stream"
        assert response.headers["cache-control"] == "no-cache"
        # Without this a buffering proxy holds pings back and it looks hung.
        assert response.headers["x-accel-buffering"] == "no"

    @pytest.mark.asyncio
    async def test_resolves_the_record_without_holding_a_session(
        self, live_client: AsyncClient
    ) -> None:
        """SQLite has one pooled connection; a held session would deadlock ingest."""
        await _seed_two_records(live_client)

        await records_router.stream_record_events(
            record_id="record-a",
            request=_StubRequest(),  # type: ignore[arg-type]
            bus=get_run_event_bus(),
        )

        # Ingest must still work while the stream response is alive.
        await _ingest(live_client, "run-1", [_span_end("b-gate", at=6)])


class TestPingStream:
    """The invalidation generator itself."""

    @pytest.mark.asyncio
    async def test_emits_initial_ping_immediately(self) -> None:
        """A late joiner must fetch without waiting for the next change."""
        bus = InMemoryRunEventBus()
        await bus.publish("run-1")

        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]

        assert _parse(await anext(stream)) == {
            "record_id": "record-a",
            "run_id": "run-1",
            "rev": 1,
            "heartbeat": False,
        }
        await stream.aclose()

    @pytest.mark.asyncio
    async def test_pings_when_the_run_changes(self) -> None:
        bus = InMemoryRunEventBus()
        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        pending = asyncio.create_task(anext(stream))  # type: ignore[arg-type]
        await asyncio.sleep(0)
        await bus.publish("run-1")

        assert _parse(await asyncio.wait_for(pending, timeout=2))["rev"] == 1
        await stream.aclose()

    @pytest.mark.asyncio
    async def test_heartbeat_is_a_data_frame_not_a_comment(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The client cannot see SSE comments.

        EventSource never times out a silent socket, so a browser can only
        tell an idle backend from a dead one if the heartbeat reaches
        `onmessage` — which a `:` comment does not.
        """
        monkeypatch.setattr(records_router, "KEEPALIVE_SECONDS", 0.01)
        bus = InMemoryRunEventBus()
        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        frame = _parse(await asyncio.wait_for(anext(stream), timeout=2))  # type: ignore[arg-type]

        assert frame["heartbeat"] is True
        assert frame["record_id"] == "record-a"
        await stream.aclose()

    @pytest.mark.asyncio
    async def test_real_pings_are_not_marked_as_heartbeats(self) -> None:
        """Otherwise the client would never refresh its 'updated' readout."""
        bus = InMemoryRunEventBus()
        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        pending = asyncio.create_task(anext(stream))  # type: ignore[arg-type]
        await asyncio.sleep(0)
        await bus.publish("run-1")

        assert _parse(await asyncio.wait_for(pending, timeout=2))["heartbeat"] is False
        await stream.aclose()

    @pytest.mark.asyncio
    async def test_stops_when_the_client_disconnects(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """The only cleanup trigger there is -- see ADR-0004."""
        monkeypatch.setattr(records_router, "KEEPALIVE_SECONDS", 0.01)
        request = _StubRequest()
        bus = InMemoryRunEventBus()
        stream = records_router._ping_stream(request, bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        request.disconnected = True

        with pytest.raises(StopAsyncIteration):
            await asyncio.wait_for(anext(stream), timeout=2)  # type: ignore[arg-type]

    @pytest.mark.asyncio
    async def test_sibling_record_activity_also_pings(self) -> None:
        """Known cost of keying the bus by run: over-notification, never under."""
        bus = InMemoryRunEventBus()
        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        pending = asyncio.create_task(anext(stream))  # type: ignore[arg-type]
        await asyncio.sleep(0)
        # A change to record-b, in the same run.
        await bus.publish("run-1")

        assert _parse(await asyncio.wait_for(pending, timeout=2))["record_id"] == "record-a"
        await stream.aclose()


def _parse(frame: str) -> dict[str, Any]:
    assert frame.startswith("data: ") and frame.endswith("\n\n")
    return json.loads(frame[len("data: "):])


class TestPublishOrdering:
    """The subtlest correctness point in the design.

    `get_session` commits in FastAPI's dependency teardown, after the route
    handler returns. If the bus published inline, a subscriber would wake,
    refetch pre-commit data, see nothing new, and never be told again.

    Note this cannot be verified by "read through a second session at
    publish time": SQLite runs on a StaticPool, so every session shares one
    connection and would see uncommitted writes anyway. So the wiring is
    checked structurally, and the guarantee it exists for is checked
    end-to-end.
    """

    @pytest.mark.asyncio
    async def test_publish_is_deferred_to_a_background_task(self) -> None:
        """Not called inline -- background tasks run after session teardown."""
        published: list[str] = []

        class SpyBus:
            async def publish(self, run_id: str) -> None:
                published.append(run_id)

            async def wait(self, run_id: str, since_rev: int) -> int:  # pragma: no cover
                raise NotImplementedError

            def current_rev(self, run_id: str) -> int:  # pragma: no cover
                return 0

        class StubIngest:
            async def ingest_events(self, request: Any) -> Any:
                return IngestResponse(accepted=1, run_id=request.run_id)

        background = BackgroundTasks()
        bus = SpyBus()

        await ingest_router.ingest_events(
            request=IngestRequest(run_id="run-x", events=[]),
            background=background,
            ingest_service=StubIngest(),  # type: ignore[arg-type]
            bus=bus,  # type: ignore[arg-type]
        )

        assert published == [], "publish must not run inline, before the commit"
        assert len(background.tasks) == 1

        await background()

        assert published == ["run-x"]

    @pytest.mark.asyncio
    async def test_data_is_present_by_the_time_a_ping_arrives(
        self, live_client: AsyncClient
    ) -> None:
        """The user-visible contract: pinged means fetchable."""
        await _seed_two_records(live_client)
        bus = get_run_event_bus()
        stream = records_router._ping_stream(_StubRequest(), bus, "record-a", "run-1")  # type: ignore[arg-type]
        await anext(stream)

        pending = asyncio.create_task(anext(stream))  # type: ignore[arg-type]
        await asyncio.sleep(0)

        await _ingest(
            live_client,
            "run-1",
            [_span_start("a-judge", "judge", parent_id="record-a", at=5)],
        )
        await asyncio.wait_for(pending, timeout=5)

        fetched = (await live_client.get("/api/v1/records/record-a")).json()
        await stream.aclose()

        assert "a-judge" in [c["id"] for c in fetched["root"]["children"]]
