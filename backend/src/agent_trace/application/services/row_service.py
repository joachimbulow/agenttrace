"""Row projection service.

A row is one item of work travelling through the pipeline -- the unit the
graph canvas renders. It is **not** a stored entity: a row is a span, and
`row_id` is that span's id. See
`docs/decisions/0002-row-as-unit-of-observation.md` for why a run was the
wrong unit to watch.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from ...domain.entities import SpanEvent, TraceNode
from ...domain.services import TreeBuilder
from ...domain.value_objects import SpanType
from ..dto.schemas import (
    RowListResponse,
    RowStatusSchema,
    RowSummary,
    RowTreeResponse,
    SpanEventResponse,
    SpanTypeSchema,
    TraceNodeResponse,
)

if TYPE_CHECKING:
    from ...domain.interfaces.repositories import (
        IRunRepository,
        ISpanEventRepository,
        ITraceNodeRepository,
    )

# Attribute stamped by the workflow's LangChain callback bridge
# (workflows/src/agent_workflows/utils/tracing.py) onto exactly the spans
# that represent one record's own graph invocation. Its presence is what
# makes a span a row root.
ROW_MARKER_ATTRIBUTE = "record_id"

ERROR_EVENT_TYPE = "error"

_SPAN_TYPE_MAP = {
    SpanType.AGENT_RUN: SpanTypeSchema.AGENT_RUN,
    SpanType.STEP: SpanTypeSchema.STEP,
    SpanType.TOOL_CALL: SpanTypeSchema.TOOL_CALL,
    SpanType.LLM_CALL: SpanTypeSchema.LLM_CALL,
}


class RowService:
    """Application service for the row projection."""

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

    async def resolve_run_id(self, row_id: str) -> str | None:
        """Find which run a row belongs to.

        Used by the SSE route at subscribe time, because the invalidation
        bus is keyed by run. Deliberately a single cheap lookup so the
        stream can release its database session before it starts
        streaming -- SQLite runs on a StaticPool with one shared
        connection, and holding it open for the life of a stream would
        deadlock ingest.

        Args:
            row_id: Row identifier (a span id).

        Returns:
            The run id, or None if no such span exists.
        """
        node = await self._node_repo.get(row_id)
        return node.run_id if node else None

    async def list_rows(self, run_id: str) -> RowListResponse | None:
        """List the rows in a run.

        Args:
            run_id: Run identifier.

        Returns:
            RowListResponse, or None if the run does not exist.
        """
        run = await self._run_repo.get(run_id)
        if not run:
            return None

        nodes = await self._node_repo.list_by_run(run_id)
        if not nodes:
            return RowListResponse(run_id=run_id, rows=[])

        roots = TreeBuilder.build_tree(nodes)
        row_roots = self._select_row_roots(roots)
        if not row_roots:
            return RowListResponse(run_id=run_id, rows=[])

        # One query for every event in the run rather than one per span:
        # this list is refetched on every invalidation ping.
        events_by_node = await self._event_repo.list_by_nodes([n.id for n in nodes])

        return RowListResponse(
            run_id=run_id,
            rows=[self._to_summary(root, events_by_node) for root in row_roots],
        )

    async def get_row(self, row_id: str) -> RowTreeResponse | None:
        """Get a row's full subtree, events included.

        Args:
            row_id: Row identifier (a span id).

        Returns:
            RowTreeResponse, or None if no such span exists.
        """
        row_node = await self._node_repo.get(row_id)
        if not row_node:
            return None

        # The tree has to be assembled from the whole run: parent/child
        # links live on the nodes, and there is no subtree query.
        nodes = await self._node_repo.list_by_run(row_node.run_id)
        roots = TreeBuilder.build_tree(nodes)
        root = TreeBuilder.find_node(roots, row_id)
        if root is None:
            return None

        subtree = TreeBuilder.flatten_tree([root])
        events_by_node = await self._event_repo.list_by_nodes([n.id for n in subtree])

        return RowTreeResponse(
            row_id=row_id,
            run_id=root.run_id,
            status=self._derive_status(root, events_by_node),
            root=self._node_to_response(root, events_by_node),
        )

    @staticmethod
    def _select_row_roots(roots: list[TraceNode]) -> list[TraceNode]:
        """Pick the spans that count as rows, most specific rule first.

        1. Spans carrying the row marker attribute. This is the real case:
           the Primo workflow stamps `record_id` onto exactly one span per
           CSV record.
        2. Otherwise the run roots' direct children -- so a program traced
           with the bare SDK, which stamps nothing, still shows its
           top-level units of work as rows instead of an empty list.
        3. Otherwise the run roots themselves, for a single-span run.

        Args:
            roots: Run root nodes with children populated.

        Returns:
            Row root nodes, ordered by start time.
        """
        marked = [
            node
            for node in TreeBuilder.flatten_tree(roots)
            if ROW_MARKER_ATTRIBUTE in (node.attributes or {})
        ]
        if marked:
            return sorted(marked, key=lambda n: (n.started_at, n.id))

        children = [child for root in roots for child in root.children]
        if children:
            return sorted(children, key=lambda n: (n.started_at, n.id))

        return sorted(roots, key=lambda n: (n.started_at, n.id))

    @classmethod
    def _derive_status(
        cls,
        root: TraceNode,
        events_by_node: dict[str, list[SpanEvent]],
    ) -> RowStatusSchema:
        """Derive a row's status from its subtree.

        Error wins over completion: a row whose root closed but which
        contains a failed span is an error, not a success.
        """
        for node in TreeBuilder.flatten_tree([root]):
            for event in events_by_node.get(node.id, []):
                if event.event_type == ERROR_EVENT_TYPE:
                    return RowStatusSchema.ERROR

        if root.ended_at is not None:
            return RowStatusSchema.COMPLETED
        return RowStatusSchema.RUNNING

    @classmethod
    def _to_summary(
        cls,
        root: TraceNode,
        events_by_node: dict[str, list[SpanEvent]],
    ) -> RowSummary:
        """Convert a row root node to a list summary."""
        attributes = root.attributes or {}
        record_id = attributes.get(ROW_MARKER_ATTRIBUTE)
        policy_id = attributes.get("policy_id")

        return RowSummary(
            row_id=root.id,
            run_id=root.run_id,
            name=root.name,
            record_id=str(record_id) if record_id is not None else None,
            policy_id=str(policy_id) if policy_id is not None else None,
            status=cls._derive_status(root, events_by_node),
            started_at=root.started_at,
            ended_at=root.ended_at,
            duration_ms=root.duration_ms,
            node_count=TreeBuilder.count_nodes([root]),
        )

    @classmethod
    def _node_to_response(
        cls,
        node: TraceNode,
        events_by_node: dict[str, list[SpanEvent]],
    ) -> TraceNodeResponse:
        """Convert a domain node and its subtree to the response DTO.

        Children are ordered by start time so the canvas layout stays
        stable between ticks -- an unchanged subtree must not reshuffle.
        """
        event_responses = [
            SpanEventResponse(
                id=e.id,
                event_type=e.event_type,
                timestamp=e.timestamp,
                payload=e.payload,
            )
            for e in events_by_node.get(node.id, [])
        ]

        children = sorted(node.children, key=lambda n: (n.started_at, n.id))

        return TraceNodeResponse(
            id=node.id,
            name=node.name,
            span_type=_SPAN_TYPE_MAP.get(node.span_type, SpanTypeSchema.STEP),
            started_at=node.started_at,
            ended_at=node.ended_at,
            duration_ms=node.duration_ms,
            attributes=node.attributes,
            children=[cls._node_to_response(child, events_by_node) for child in children],
            events=event_responses,
        )
