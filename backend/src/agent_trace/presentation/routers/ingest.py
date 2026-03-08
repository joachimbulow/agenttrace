from __future__ import annotations

from fastapi import APIRouter, Depends

from ...application.dto import IngestRequest, IngestResponse
from ...application.services import IngestService
from ..dependencies import get_ingest_service

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post("/events", response_model=IngestResponse, status_code=202)
async def ingest_events(
    request: IngestRequest,
    ingest_service: IngestService = Depends(get_ingest_service),
) -> IngestResponse:
    """Ingest a batch of trace events.

    This endpoint accepts events from the SDK and stores them.
    Events are processed asynchronously.

    Args:
        request: Ingest request with run_id and events.
        ingest_service: Injected IngestService.

    Returns:
        Ingest response with accepted count.
    """
    return await ingest_service.ingest_events(request)