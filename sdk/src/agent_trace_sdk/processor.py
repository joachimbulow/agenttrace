from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
from collections import deque

from .domain.interfaces import IEventExporter, ExportBatch, ExportEvent


@dataclass
class BatchConfig:
    """Configuration for batch processing.
    
    Attributes:
        max_size: Maximum batch size before forcing export.
        timeout_ms: Maximum time to wait before exporting partial batch.
    """
    max_size: int = 100
    timeout_ms: int = 5000


class BatchSpanProcessor:
    """Processor that batches events before exporting.
    
    Collects events up to max_size or timeout, then exports them in a batch.
    """
    
    def __init__(
        self,
        exporter: IEventExporter,
        config: BatchConfig | None = None,
    ) -> None:
        """Initialize batch processor.
        
        Args:
            exporter: The exporter to use for sending events.
            config: Batch configuration.
        """
        self._exporter = exporter
        self._config = config or BatchConfig()
        self._events: deque[ExportEvent] = deque()
        self._run_id: str | None = None
        self._run_name: str | None = None  # Run name for first batch
        self._lock = asyncio.Lock()
        self._flush_task: asyncio.Task | None = None
    
    def set_run_id(self, run_id: str, run_name: str | None = None) -> None:
        """Set the current run ID and optional name.
        
        Args:
            run_id: The run ID for subsequent events.
            run_name: Optional run name (sent with first batch).
        """
        self._run_id = run_id
        self._run_name = run_name
    
    async def add_event(self, event: ExportEvent) -> None:
        """Add an event to the batch.
        
        Args:
            event: The event to add.
        """
        async with self._lock:
            self._events.append(event)
            
            # Check if we should flush
            if len(self._events) >= self._config.max_size:
                await self._flush_internal()
    
    async def flush(self) -> None:
        """Flush all pending events."""
        async with self._lock:
            await self._flush_internal()
    
    async def _flush_internal(self) -> None:
        """Internal flush without lock (caller must hold lock)."""
        if not self._events or not self._run_id:
            return
        
        # Create batch from pending events
        events = list(self._events)
        self._events.clear()
        
        # Include run_name only for first batch (then clear it)
        run_name = self._run_name
        self._run_name = None  # Only send once
        
        batch = ExportBatch(
            run_id=self._run_id,
            events=events,
            run_name=run_name,
        )
        
        # Export (don't hold lock during network call)
        await self._exporter.export(batch)
    
    async def close(self) -> None:
        """Flush pending events and close exporter."""
        await self.flush()
        await self._exporter.close()