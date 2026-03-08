from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid

from ..value_objects import RunStatus


def _utcnow() -> datetime:
    """Get current UTC time (Python 3.12+ compatible).
    
    datetime.utcnow() is deprecated in Python 3.12+.
    Use datetime.now(timezone.utc) instead.
    """
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class AgentRun:
    """Root aggregate representing a single agent execution trace."""

    id: str
    name: str
    status: RunStatus
    started_at: datetime
    ended_at: datetime | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=_utcnow)
    updated_at: datetime = field(default_factory=_utcnow)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.id:
            raise ValueError("AgentRun id cannot be empty")
        if not self.name:
            raise ValueError("AgentRun name cannot be empty")
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("ended_at cannot be before started_at")

    @property
    def duration_ms(self) -> float | None:
        """Calculate duration in milliseconds."""
        if self.ended_at is None:
            return None
        delta = self.ended_at - self.started_at
        return delta.total_seconds() * 1000

    def complete(self, ended_at: datetime | None = None) -> AgentRun:
        """Mark run as completed."""
        return AgentRun(
            id=self.id,
            name=self.name,
            status=RunStatus.COMPLETED,
            started_at=self.started_at,
            ended_at=ended_at or _utcnow(),
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=_utcnow(),
        )

    def fail(self, ended_at: datetime | None = None) -> AgentRun:
        """Mark run as failed."""
        return AgentRun(
            id=self.id,
            name=self.name,
            status=RunStatus.FAILED,
            started_at=self.started_at,
            ended_at=ended_at or _utcnow(),
            metadata=self.metadata,
            created_at=self.created_at,
            updated_at=_utcnow(),
        )

    @classmethod
    def create(cls, name: str, metadata: dict[str, Any] | None = None) -> AgentRun:
        """Factory method to create a new run."""
        now = _utcnow()
        return cls(
            id=str(uuid.uuid4()),
            name=name,
            status=RunStatus.RUNNING,
            started_at=now,
            metadata=metadata or {},
            created_at=now,
            updated_at=now,
        )