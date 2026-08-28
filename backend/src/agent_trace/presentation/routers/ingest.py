from __future__ import annotations

from fastapi import APIRouter, BackgroundTasks, Depends

from ...application.dto import IngestRequest, IngestResponse
from ...application.services import IngestService
from ...domain.interfaces.bus import IRunEventBus
from ..dependencies import get_event_bus, get_ingest_service

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/events", response_model=IngestResponse, status_code=202)
async def ingest_events(
    request: IngestRequest,
    background: BackgroundTasks,
    ingest_service: IngestService = Depends(get_ingest_service),
    bus: IRunEventBus = Depends(get_event_bus),
) -> IngestResponse:
    """Ingest a batch of trace events and notify live subscribers.

    The bus publish is deferred to a background task on purpose. The
    database session commits in FastAPI's dependency teardown, *after*
    this handler returns; background tasks run later still. Publishing
    inline would wake subscribers before the commit, so they would refetch
    pre-commit data, see nothing new, and never be told again.

    Args:
        request: Ingest request with run_id and events.
        background: FastAPI background tasks, used to publish post-commit.
        ingest_service: Injected IngestService.
        bus: Injected run invalidation bus.

    Returns:
        Ingest response with accepted count.
    """
    response = await ingest_service.ingest_events(request)
    background.add_task(bus.publish, request.run_id)
    return response