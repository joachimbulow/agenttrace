from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Annotated

from ...application.dto import (
    RunListResponse,
    RunResponse,
    TraceTreeResponse,
)
from ...application.services import RunService
from ..dependencies import get_run_service

router = APIRouter(prefix="/runs", tags=["runs"])


@router.get("", response_model=RunListResponse)
async def list_runs(
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
    status: str | None = Query(
        None, description="Filter by status (running, completed, failed)"
    ),
    run_service: RunService = Depends(get_run_service),
) -> RunListResponse:
    """List all runs with pagination.

    Args:
        limit: Maximum number of runs to return (1-100).
        offset: Number of runs to skip.
        status: Optional filter by status.
        run_service: Injected RunService.

    Returns:
        List of runs with pagination info.
    """
    return await run_service.list_runs(limit=limit, offset=offset, status=status)


@router.get("/{run_id}", response_model=RunResponse)
async def get_run(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
) -> RunResponse:
    """Get a single run by ID.

    Args:
        run_id: Unique run identifier.
        run_service: Injected RunService.

    Returns:
        Run details.

    Raises:
        HTTPException: 404 if run not found.
    """
    run = await run_service.get_run(run_id)
    if run is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return run


@router.get("/{run_id}/tree", response_model=TraceTreeResponse)
async def get_run_tree(
    run_id: str,
    run_service: RunService = Depends(get_run_service),
) -> TraceTreeResponse:
    """Get the trace tree for a run.

    Args:
        run_id: Unique run identifier.
        run_service: Injected RunService.

    Returns:
        Hierarchical trace tree.

    Raises:
        HTTPException: 404 if run not found.
    """
    tree = await run_service.get_run_tree(run_id)
    if tree is None:
        raise HTTPException(status_code=404, detail=f"Run {run_id} not found")
    return tree