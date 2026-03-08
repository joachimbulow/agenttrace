from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ExportEvent:
    """Event to be exported by SDK.
    
    This format matches the Backend's IngestRequest schema.
    Backend expects:
        {
            "type": "span_start" | "span_end" | "span_event",
            "data": {
                "span_id": "...",
                "timestamp": "...",
                # other fields
            }
        }
    """
    
    event_type: str  # "span_start", "span_end", "span_event"
    span_id: str
    timestamp: str  # ISO format
    data: dict[str, Any]
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to Backend-compatible format.
        
        Backend expects 'type' (not 'event_type') and
        span_id/timestamp inside 'data'.
        """
        # Merge span_id and timestamp into data
        merged_data = {
            "span_id": self.span_id,
            "timestamp": self.timestamp,
            **self.data,
        }
        
        return {
            "type": self.event_type,  # Backend expects "type", not "event_type"
            "data": merged_data,
        }


@dataclass(frozen=True)
class ExportBatch:
    """Batch of events to export."""
    
    run_id: str
    events: list[ExportEvent]
    run_name: str | None = None  # Optional run name for first event
    
    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for Backend API.
        
        Backend IngestRequest format:
            {
                "run_id": str,
                "run_name": str | None,
                "events": list[IngestEvent]
            }
        """
        result: dict[str, Any] = {
            "run_id": self.run_id,
            "events": [e.to_dict() for e in self.events],
        }
        if self.run_name is not None:
            result["run_name"] = self.run_name
        return result


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