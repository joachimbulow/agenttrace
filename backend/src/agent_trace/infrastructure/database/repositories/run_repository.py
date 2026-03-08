from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from agent_trace.domain.entities import AgentRun, SpanEvent, TraceNode
from agent_trace.domain.interfaces.repositories import (
    IRunRepository,
    ISpanEventRepository,
    ITraceNodeRepository,
)
from agent_trace.domain.value_objects import RunStatus, SpanType
from agent_trace.infrastructure.database.models import (
    RunModel,
    SpanEventModel,
    TraceNodeModel,
)

if TYPE_CHECKING:
    from collections.abc import Sequence


def _utcnow() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


class RunRepository(IRunRepository):
    """SQLAlchemy implementation of IRunRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def save(self, run: AgentRun) -> AgentRun:
        """Save a run to the database.

        Args:
            run: Domain entity to save.

        Returns:
            Saved domain entity.
        """
        model = RunModel(
            id=run.id,
            name=run.name,
            status=run.status.value,
            started_at=run.started_at,
            ended_at=run.ended_at,
            metadata_json=run.metadata,
            created_at=run.created_at,
            updated_at=run.updated_at,
        )
        self._session.add(model)
        await self._session.flush()
        return self._model_to_entity(model)

    async def get(self, run_id: str) -> AgentRun | None:
        """Get a run by ID.

        Args:
            run_id: Unique identifier.

        Returns:
            Domain entity if found, None otherwise.
        """
        stmt = select(RunModel).where(RunModel.id == run_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def list(
        self,
        limit: int = 20,
        offset: int = 0,
        status: str | None = None,
    ) -> list[AgentRun]:
        """List runs with pagination.

        Args:
            limit: Maximum number to return.
            offset: Number to skip.
            status: Filter by status if provided.

        Returns:
            List of domain entities.
        """
        stmt = select(RunModel).order_by(RunModel.created_at.desc())

        if status:
            stmt = stmt.where(RunModel.status == status)

        stmt = stmt.limit(limit).offset(offset)
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._model_to_entity(m) for m in models]

    async def count(self, status: str | None = None) -> int:
        """Count total runs.

        Args:
            status: Filter by status if provided.

        Returns:
            Total count.
        """
        stmt = select(func.count(RunModel.id))
        if status:
            stmt = stmt.where(RunModel.status == status)
        result = await self._session.execute(stmt)
        return result.scalar_one()

    async def update(self, run: AgentRun) -> AgentRun:
        """Update an existing run.

        Args:
            run: Domain entity with updated values.

        Returns:
            Updated domain entity.
        """
        stmt = select(RunModel).where(RunModel.id == run.id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()

        if not model:
            raise ValueError(f"Run {run.id} not found")

        model.status = run.status.value
        model.ended_at = run.ended_at
        model.metadata_json = run.metadata
        model.updated_at = _utcnow()

        await self._session.flush()
        return self._model_to_entity(model)

    def _model_to_entity(self, model: RunModel) -> AgentRun:
        """Convert ORM model to domain entity.

        Args:
            model: SQLAlchemy model.

        Returns:
            Domain entity.
        """
        return AgentRun(
            id=model.id,
            name=model.name,
            status=RunStatus(model.status),
            started_at=model.started_at,
            ended_at=model.ended_at,
            metadata=model.metadata_json or {},
            created_at=model.created_at,
            updated_at=model.updated_at,
        )


class TraceNodeRepository(ITraceNodeRepository):
    """SQLAlchemy implementation of ITraceNodeRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def save(self, node: TraceNode) -> TraceNode:
        """Save a trace node to the database.

        Args:
            node: Domain entity to save.

        Returns:
            Saved domain entity.
        """
        model = TraceNodeModel(
            id=node.id,
            run_id=node.run_id,
            parent_id=node.parent_id,
            name=node.name,
            span_type=node.span_type.value,
            started_at=node.started_at,
            ended_at=node.ended_at,
            attributes_json=node.attributes,
        )
        # Use merge to handle both insert and update
        merged = await self._session.merge(model)
        await self._session.flush()
        return self._model_to_entity(merged)

    async def get(self, node_id: str) -> TraceNode | None:
        """Get a trace node by ID.

        Args:
            node_id: Unique identifier.

        Returns:
            Domain entity if found, None otherwise.
        """
        stmt = select(TraceNodeModel).where(TraceNodeModel.id == node_id)
        result = await self._session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._model_to_entity(model) if model else None

    async def list_by_run(self, run_id: str) -> list[TraceNode]:
        """List all nodes for a run.

        Args:
            run_id: Run identifier.

        Returns:
            List of domain entities.
        """
        stmt = (
            select(TraceNodeModel)
            .where(TraceNodeModel.run_id == run_id)
            .order_by(TraceNodeModel.started_at)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._model_to_entity(m) for m in models]

    async def get_tree(self, run_id: str) -> TraceNode | None:
        """Get the root node with all children loaded.

        Args:
            run_id: Run identifier.

        Returns:
            Root node with children, None if no nodes exist.
        """
        nodes = await self.list_by_run(run_id)
        if not nodes:
            return None

        # Build tree using domain service
        from agent_trace.domain.services import TreeBuilder

        roots = TreeBuilder.build_tree(nodes)

        return roots[0] if roots else None

    def _model_to_entity(self, model: TraceNodeModel) -> TraceNode:
        """Convert ORM model to domain entity.

        Args:
            model: SQLAlchemy model.

        Returns:
            Domain entity.
        """
        return TraceNode(
            id=model.id,
            run_id=model.run_id,
            parent_id=model.parent_id,
            name=model.name,
            span_type=SpanType(model.span_type),
            started_at=model.started_at,
            ended_at=model.ended_at,
            attributes=model.attributes_json or {},
        )


class SpanEventRepository(ISpanEventRepository):
    """SQLAlchemy implementation of ISpanEventRepository."""

    def __init__(self, session: AsyncSession) -> None:
        """Initialize repository with database session.

        Args:
            session: SQLAlchemy async session.
        """
        self._session = session

    async def save(self, event: SpanEvent) -> SpanEvent:
        """Save a span event to the database.

        Args:
            event: Domain entity to save.

        Returns:
            Saved domain entity.
        """
        model = SpanEventModel(
            id=event.id,
            node_id=event.node_id,
            event_type=event.event_type,
            timestamp=event.timestamp,
            payload_json=event.payload,
        )
        self._session.add(model)
        await self._session.flush()
        return self._model_to_entity(model)

    async def list_by_node(self, node_id: str) -> list[SpanEvent]:
        """List all events for a node.

        Args:
            node_id: Node identifier.

        Returns:
            List of domain entities.
        """
        stmt = (
            select(SpanEventModel)
            .where(SpanEventModel.node_id == node_id)
            .order_by(SpanEventModel.timestamp)
        )
        result = await self._session.execute(stmt)
        models = result.scalars().all()
        return [self._model_to_entity(m) for m in models]

    def _model_to_entity(self, model: SpanEventModel) -> SpanEvent:
        """Convert ORM model to domain entity.

        Args:
            model: SQLAlchemy model.

        Returns:
            Domain entity.
        """
        return SpanEvent(
            id=model.id,
            node_id=model.node_id,
            event_type=model.event_type,
            timestamp=model.timestamp,
            payload=model.payload_json or {},
        )