from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..entities import AgentRun, SpanEvent, TraceNode


class IRunRepository(ABC):
    """Abstract repository for AgentRun persistence."""

    @abstractmethod
    async def save(self, run: AgentRun) -> AgentRun:
        """Persist a run.

        Args:
            run: The run to save.

        Returns:
            The saved run (with updated timestamps if applicable).
        """
        ...

    @abstractmethod
    async def get(self, run_id: str) -> AgentRun | None:
        """Retrieve a run by ID.

        Args:
            run_id: The unique identifier of the run.

        Returns:
            The run if found, None otherwise.
        """
        ...

    @abstractmethod
    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[AgentRun]:
        """List runs with pagination.

        Args:
            limit: Maximum number of runs to return.
            offset: Number of runs to skip.
            status: Filter by status if provided.

        Returns:
            List of runs.
        """
        ...

    @abstractmethod
    async def count(self, status: str | None = None) -> int:
        """Count total runs.

        Args:
            status: Filter by status if provided.

        Returns:
            Total count of runs.
        """
        ...


class ITraceNodeRepository(ABC):
    """Abstract repository for TraceNode persistence."""

    @abstractmethod
    async def save(self, node: TraceNode) -> TraceNode:
        """Persist a trace node."""
        ...

    @abstractmethod
    async def get(self, node_id: str) -> TraceNode | None:
        """Retrieve a trace node by ID."""
        ...

    @abstractmethod
    async def list_by_run(self, run_id: str) -> list[TraceNode]:
        """List all nodes for a run."""
        ...

    @abstractmethod
    async def get_tree(self, run_id: str) -> TraceNode | None:
        """Get the root node with all children loaded."""
        ...


class ISpanEventRepository(ABC):
    """Abstract repository for SpanEvent persistence."""

    @abstractmethod
    async def save(self, event: SpanEvent) -> SpanEvent:
        """Persist a span event."""
        ...

    @abstractmethod
    async def list_by_node(self, node_id: str) -> list[SpanEvent]:
        """List all events for a node."""
        ...

    @abstractmethod
    async def list_by_nodes(self, node_ids: list[str]) -> dict[str, list[SpanEvent]]:
        """List events for many nodes in one query.

        The row endpoints are refetched on every invalidation ping, so the
        per-node query this replaces would run once per span per ping.

        Args:
            node_ids: Node identifiers to fetch events for.

        Returns:
            Map of node id to its events, ordered by timestamp. Nodes with
            no events are absent from the map.
        """
        ...
