from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.entities import AgentRun, SpanEvent, TraceNode
from ...domain.services import TreeBuilder
from ...domain.value_objects import RunStatus, SpanType
from ..dto.schemas import (
    RunListResponse,
    RunResponse,
    RunStatusSchema,
    SpanEventResponse,
    SpanTypeSchema,
    TraceNodeResponse,
    TraceTreeResponse,
)

if TYPE_CHECKING:
    from ...domain.interfaces.repositories import (
        IRunRepository,
        ISpanEventRepository,
        ITraceNodeRepository,
    )


class RunService:
    """Application service for run management.

    Coordinates between repositories and domain services to handle
    run-related use cases.
    """

    def __init__(
        self,
        run_repo: IRunRepository,
        node_repo: ITraceNodeRepository,
        event_repo: ISpanEventRepository,
    ) -> None:
        """Initialize service with repositories.

        Args:
            run_repo: Repository for runs.
            node_repo: Repository for trace nodes.
            event_repo: Repository for span events.
        """
        self._run_repo = run_repo
        self._node_repo = node_repo
        self._event_repo = event_repo

    async def get_run(self, run_id: str) -> RunResponse | None:
        """Get a single run by ID.

        Args:
            run_id: Unique run identifier.

        Returns:
            RunResponse if found, None otherwise.
        """
        run = await self._run_repo.get(run_id)
        if not run:
            return None

        # Get node count
        nodes = await self._node_repo.list_by_run(run_id)

        return self._run_to_response(run, len(nodes))

    async def list_runs(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> RunListResponse:
        """List runs with pagination.

        Args:
            limit: Maximum number to return.
            offset: Number to skip.
            status: Filter by status if provided.

        Returns:
            RunListResponse with runs and pagination info.
        """
        runs = await self._run_repo.list(limit=limit, offset=offset, status=status)
        total = await self._run_repo.count(status=status)

        run_responses = [
            self._run_to_response(run, 0)  # Node count not needed for list
            for run in runs
        ]

        return RunListResponse(
            runs=run_responses,
            total=total,
            limit=limit,
            offset=offset,
        )

    async def get_run_tree(self, run_id: str) -> TraceTreeResponse | None:
        """Get the trace tree for a run.

        Args:
            run_id: Unique run identifier.

        Returns:
            TraceTreeResponse if found, None otherwise.
        """
        # Verify run exists
        run = await self._run_repo.get(run_id)
        if not run:
            return None

        # Get all nodes
        nodes = await self._node_repo.list_by_run(run_id)
        if not nodes:
            return TraceTreeResponse(run_id=run_id, root=None)

        # Build tree
        roots = TreeBuilder.build_tree(nodes)
        if not roots:
            return TraceTreeResponse(run_id=run_id, root=None)

        # Get events for all nodes
        node_events: dict[str, list[SpanEvent]] = {}
        for node in nodes:
            events = await self._event_repo.list_by_node(node.id)
            node_events[node.id] = events

        # Convert to response (use first root if multiple exist)
        root_response = self._node_to_response(roots[0], node_events)

        return TraceTreeResponse(run_id=run_id, root=root_response)

    def _run_to_response(self, run: AgentRun, node_count: int) -> RunResponse:
        """Convert domain entity to response DTO.

        Args:
            run: Domain entity.
            node_count: Number of nodes in the run.

        Returns:
            Response DTO.
        """
        # Map domain RunStatus to schema RunStatusSchema
        status_map = {
            RunStatus.RUNNING: RunStatusSchema.RUNNING,
            RunStatus.COMPLETED: RunStatusSchema.COMPLETED,
            RunStatus.FAILED: RunStatusSchema.FAILED,
        }
        status_schema = status_map.get(run.status, RunStatusSchema.RUNNING)

        return RunResponse(
            id=run.id,
            name=run.name,
            status=status_schema,
            started_at=run.started_at,
            ended_at=run.ended_at,
            duration_ms=run.duration_ms,
            metadata=run.metadata,
            node_count=node_count if node_count > 0 else None,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )

    def _node_to_response(
        self,
        node: TraceNode,
        node_events: dict[str, list[SpanEvent]],
    ) -> TraceNodeResponse:
        """Convert domain node to response DTO recursively.

        Args:
            node: Domain entity.
            node_events: Map of node ID to events.

        Returns:
            Response DTO with children and events.
        """
        events = node_events.get(node.id, [])
        event_responses = [
            SpanEventResponse(
                id=e.id,
                event_type=e.event_type,
                timestamp=e.timestamp,
                payload=e.payload,
            )
            for e in events
        ]

        children_responses = [
            self._node_to_response(child, node_events)
            for child in node.children
        ]

        # Map domain SpanType to schema SpanTypeSchema
        span_type_map = {
            SpanType.AGENT_RUN: SpanTypeSchema.AGENT_RUN,
            SpanType.STEP: SpanTypeSchema.STEP,
            SpanType.TOOL_CALL: SpanTypeSchema.TOOL_CALL,
            SpanType.LLM_CALL: SpanTypeSchema.LLM_CALL,
        }
        span_type_schema = span_type_map.get(node.span_type, SpanTypeSchema.STEP)

        return TraceNodeResponse(
            id=node.id,
            name=node.name,
            span_type=span_type_schema,
            started_at=node.started_at,
            ended_at=node.ended_at,
            duration_ms=node.duration_ms,
            attributes=node.attributes,
            children=children_responses,
            events=event_responses,
        )