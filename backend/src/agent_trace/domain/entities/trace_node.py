from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from ..value_objects import SpanType


def _utcnow() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


@dataclass
class TraceNode:
    """Hierarchical trace element within a run."""

    id: str
    run_id: str
    name: str
    span_type: SpanType
    started_at: datetime
    parent_id: str | None = None
    ended_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    children: list[TraceNode] = field(default_factory=list)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.id:
            raise ValueError("TraceNode id cannot be empty")
        if not self.run_id:
            raise ValueError("TraceNode run_id cannot be empty")
        if not self.name:
            raise ValueError("TraceNode name cannot be empty")

    @property
    def duration_ms(self) -> float | None:
        """Calculate duration in milliseconds."""
        if self.ended_at is None:
            return None
        delta = self.ended_at - self.started_at
        return delta.total_seconds() * 1000

    def is_root(self) -> bool:
        """Check if this is a root node."""
        return self.parent_id is None

    def add_child(self, child: TraceNode) -> None:
        """Add a child node."""
        self.children.append(child)

    def complete(self, ended_at: datetime | None = None) -> TraceNode:
        """Mark node as completed."""
        return TraceNode(
            id=self.id,
            run_id=self.run_id,
            name=self.name,
            span_type=self.span_type,
            started_at=self.started_at,
            parent_id=self.parent_id,
            ended_at=ended_at or _utcnow(),
            attributes=self.attributes,
            children=self.children,
        )

    @classmethod
    def create(
        cls,
        run_id: str,
        name: str,
        span_type: SpanType,
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> TraceNode:
        """Factory method to create a new trace node."""
        return cls(
            id=str(uuid.uuid4()),
            run_id=run_id,
            name=name,
            span_type=span_type,
            started_at=_utcnow(),
            parent_id=parent_id,
            attributes=attributes or {},
        )