from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExportEvent:
    """Event to be exported by SDK."""

    event_type: str  # "span_start", "span_end", "event"
    span_id: str
    timestamp: str  # ISO format
    data: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "event_type": self.event_type,
            "span_id": self.span_id,
            "timestamp": self.timestamp,
            "data": self.data,
        }


@dataclass(frozen=True)
class ExportBatch:
    """Batch of events to export."""

    run_id: str
    events: list[ExportEvent]

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization."""
        return {
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self.events],
        }


class IEventExporter(ABC):
    """Abstract exporter for trace events (SDK)."""

    @abstractmethod
    async def export(self, batch: ExportBatch) -> bool:
        """Export a batch of events.

        Args:
            batch: The batch of events to export.

        Returns:
            True if export succeeded, False otherwise.

        Raises:
            ExportError: If export fails.
        """
        ...

    @abstractmethod
    async def flush(self) -> None:
        """Flush any pending events."""
        ...

    @abstractmethod
    async def close(self) -> None:
        """Close the exporter and release resources."""
        ...


class ExportError(Exception):
    """Error during event export."""
    pass
