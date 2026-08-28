from __future__ import annotations

from typing import AsyncGenerator

from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession

from ..infrastructure.bus import get_run_event_bus
from ..infrastructure.database import get_session
from ..infrastructure.database.repositories import (
    RunRepository,
    SpanEventRepository,
    TraceNodeRepository,
)
from ..domain.interfaces.bus import IRunEventBus
from ..domain.interfaces.clock import IClock, SystemClock
from ..application.services import RowService, RunService, IngestService


async def get_db_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency for database session."""
    async for session in get_session():
        yield session


def get_run_repository(
    session: AsyncSession = Depends(get_db_session),
) -> RunRepository:
    """FastAPI dependency for RunRepository.
    
    Args:
        session: AsyncSession from dependency injection.
        
    Returns:
        RunRepository instance.
    """
    return RunRepository(session)


def get_trace_node_repository(
    session: AsyncSession = Depends(get_db_session),
) -> TraceNodeRepository:
    """FastAPI dependency for TraceNodeRepository.
    
    Args:
        session: AsyncSession from dependency injection.
        
    Returns:
        TraceNodeRepository instance.
    """
    return TraceNodeRepository(session)


def get_span_event_repository(
    session: AsyncSession = Depends(get_db_session),
) -> SpanEventRepository:
    """FastAPI dependency for SpanEventRepository.
    
    Args:
        session: AsyncSession from dependency injection.
        
    Returns:
        SpanEventRepository instance.
    """
    return SpanEventRepository(session)


def get_clock() -> IClock:
    """FastAPI dependency for clock.
    
    Returns:
        SystemClock instance for production use.
    """
    return SystemClock()


def get_run_service(
    run_repo: RunRepository = Depends(get_run_repository),
    node_repo: TraceNodeRepository = Depends(get_trace_node_repository),
    event_repo: SpanEventRepository = Depends(get_span_event_repository),
) -> RunService:
    """FastAPI dependency for RunService.
    
    Args:
        run_repo: RunRepository from dependency injection.
        node_repo: TraceNodeRepository from dependency injection.
        event_repo: SpanEventRepository from dependency injection.
        
    Returns:
        RunService instance.
    """
    return RunService(run_repo, node_repo, event_repo)


def get_row_service(
    run_repo: RunRepository = Depends(get_run_repository),
    node_repo: TraceNodeRepository = Depends(get_trace_node_repository),
    event_repo: SpanEventRepository = Depends(get_span_event_repository),
) -> RowService:
    """FastAPI dependency for RowService.

    Args:
        run_repo: RunRepository from dependency injection.
        node_repo: TraceNodeRepository from dependency injection.
        event_repo: SpanEventRepository from dependency injection.

    Returns:
        RowService instance.
    """
    return RowService(run_repo, node_repo, event_repo)


def get_event_bus() -> IRunEventBus:
    """FastAPI dependency for the run invalidation bus.

    Returns the process-wide singleton, not a per-request instance -- a
    fresh bus per request would mean ingest and the stream never see each
    other.

    Returns:
        The shared IRunEventBus.
    """
    return get_run_event_bus()


def get_ingest_service(
    run_repo: RunRepository = Depends(get_run_repository),
    node_repo: TraceNodeRepository = Depends(get_trace_node_repository),
    event_repo: SpanEventRepository = Depends(get_span_event_repository),
    clock: IClock = Depends(get_clock),
) -> IngestService:
    """FastAPI dependency for IngestService.
    
    Args:
        run_repo: RunRepository from dependency injection.
        node_repo: TraceNodeRepository from dependency injection.
        event_repo: SpanEventRepository from dependency injection.
        clock: IClock from dependency injection.
        
    Returns:
        IngestService instance.
    """
    return IngestService(run_repo, node_repo, event_repo, clock)