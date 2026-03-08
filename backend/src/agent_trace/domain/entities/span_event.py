from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any
import uuid


def _utcnow() -> datetime:
    """Get current UTC time (Python 3.12+ compatible)."""
    return datetime.now(timezone.utc)


@dataclass(frozen=True)
class SpanEvent:
    """Terminal event associated with a trace node."""

    id: str
    node_id: str
    event_type: str
    timestamp: datetime
    payload: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        """Validate invariants."""
        if not self.id:
            raise ValueError("SpanEvent id cannot be empty")
        if not self.node_id:
            raise ValueError("SpanEvent node_id cannot be empty")
        if not self.event_type:
            raise ValueError("SpanEvent event_type cannot be empty")

    @classmethod
    def create(
        cls,
        node_id: str,
        event_type: str,
        payload: dict[str, Any] | None = None,
    ) -> SpanEvent:
        """Factory method to create a new event."""
        return cls(
            id=str(uuid.uuid4()),
            node_id=node_id,
            event_type=event_type,
            timestamp=_utcnow(),
            payload=payload or {},
        )