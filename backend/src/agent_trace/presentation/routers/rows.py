"""Row endpoints, including the live invalidation stream.

A row is the unit the graph canvas renders -- one item of work through the
pipeline, projected over spans already in the database. See
`docs/decisions/0002-row-as-unit-of-observation.md`.
"""
from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse

from ...application.dto import RowListResponse, RowTreeResponse
from ...application.services import RowService
from ...domain.interfaces.bus import IRunEventBus
from ...infrastructure.database import get_db
from ...infrastructure.database.repositories import (
    RunRepository,
    SpanEventRepository,
    TraceNodeRepository,
)
from ..dependencies import get_event_bus, get_row_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/rows", tags=["rows"])

# How long to block before emitting a heartbeat. Streams never terminate on
# their own (see ADR-0004), so an idle connection needs to keep proving it
# is alive -- both to intermediaries that would otherwise drop it, and to
# the client, which has no other way to tell an idle backend from a dead
# one (EventSource does not time out a silent socket).
KEEPALIVE_SECONDS = 10.0


@router.get("", response_model=RowListResponse)
async def list_rows(
    run_id: Annotated[str, Query(description="Run to list rows for")],
    row_service: RowService = Depends(get_row_service),
) -> RowListResponse:
    """List the rows in a run.

    Args:
        run_id: Run identifier.
        row_service: Injected RowService.

    Returns:
        Rows in the run, ordered by start time.

    Raises:
        HTTPException: 404 if the run does not exist.
    """
    rows = await row_service.list_rows(run_id)
    if rows is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return rows


@router.get("/{row_id}", response_model=RowTreeResponse)
async def get_row(
    row_id: str,
    row_service: RowService = Depends(get_row_service),
) -> RowTreeResponse:
    """Get a row's full subtree, event payloads included.

    This is what the canvas refetches on every invalidation ping.

    Args:
        row_id: Row identifier (the row root span's id).
        row_service: Injected RowService.

    Returns:
        The row's subtree and derived status.

    Raises:
        HTTPException: 404 if no such row exists.
    """
    row = await row_service.get_row(row_id)
    if row is None:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")
    return row


@router.get("/{row_id}/events")
async def stream_row_events(
    row_id: str,
    request: Request,
    bus: IRunEventBus = Depends(get_event_bus),
) -> StreamingResponse:
    """Subscribe to invalidation pings for a row.

    Each message means only "this row changed, refetch it" -- it carries
    no span data. See
    `docs/decisions/0001-invalidation-bus-over-event-stream.md`.

    Deliberately takes no database-session dependency. SQLite runs on a
    StaticPool with a single shared connection; a stream holding a session
    open for its lifetime would pin that connection and deadlock ingest.
    The one lookup this needs (row -> run, because the bus is keyed by
    run) happens in a session opened and closed before streaming starts.

    Args:
        row_id: Row identifier (the row root span's id).
        request: Used to detect client disconnect.
        bus: Injected run invalidation bus.

    Returns:
        A text/event-stream response.

    Raises:
        HTTPException: 404 if no such row exists.
    """
    run_id = await _resolve_run_id(row_id)
    if run_id is None:
        raise HTTPException(status_code=404, detail=f"Row {row_id} not found")

    return StreamingResponse(
        _ping_stream(request, bus, row_id, run_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            # Disable proxy buffering; without it an intermediary can hold
            # pings until its own buffer fills, which looks like a hang.
            "X-Accel-Buffering": "no",
        },
    )


async def _resolve_run_id(row_id: str) -> str | None:
    """Look up a row's run in a short-lived session.

    Not a FastAPI dependency on purpose: a `Depends`-provided session
    stays open for the whole response, which for a stream means forever.
    """
    db = get_db()
    async with db.session() as session:
        service = RowService(
            RunRepository(session),
            TraceNodeRepository(session),
            SpanEventRepository(session),
        )
        return await service.resolve_run_id(row_id)


async def _ping_stream(
    request: Request,
    bus: IRunEventBus,
    row_id: str,
    run_id: str,
) -> AsyncIterator[str]:
    """Yield invalidation pings until the client goes away.

    Emits one immediately so the client fetches without waiting for the
    first change, then blocks on the bus. Since streams never terminate on
    their own, client disconnect is the only cleanup trigger there is.
    """
    rev = bus.current_rev(run_id)
    yield _ping(row_id, run_id, rev)

    while True:
        if await request.is_disconnected():
            logger.debug("Row stream %s disconnected", row_id)
            return

        try:
            rev = await asyncio.wait_for(
                bus.wait(run_id, rev),
                timeout=KEEPALIVE_SECONDS,
            )
        except TimeoutError:
            # Nothing happened. Re-send the current rev rather than an SSE
            # comment: a comment does not reach the client's `onmessage`,
            # so it cannot be used to tell "idle backend" from "dead
            # backend". Repeating a rev is inert -- the client only acts
            # when the rev advances.
            yield _ping(row_id, run_id, rev, heartbeat=True)
            continue
        except asyncio.CancelledError:
            return

        yield _ping(row_id, run_id, rev)


def _ping(row_id: str, run_id: str, rev: int, *, heartbeat: bool = False) -> str:
    """Format one SSE frame.

    `heartbeat` marks a frame that carries no new revision, so the client
    can refresh its liveness timer without touching its "last updated"
    readout.
    """
    payload = json.dumps(
        {"row_id": row_id, "run_id": run_id, "rev": rev, "heartbeat": heartbeat}
    )
    return f"data: {payload}\n\n"
