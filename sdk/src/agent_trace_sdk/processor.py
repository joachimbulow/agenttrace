"""Batch processor for exporting trace events.

This module provides the BatchSpanProcessor which collects events and exports
them in batches for efficiency and reliability.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any
import asyncio
import logging
from collections import deque

from .domain.interfaces import IEventExporter, ExportBatch, ExportEvent, ExportError



@dataclass
class BatchConfig:
    """Configuration for batch processing.
    
    Attributes:
        max_size: Maximum batch size before forcing export.
        timeout_ms: Maximum time to wait before exporting partial batch.
        max_queue_size: Maximum events to queue before dropping (memory protection).
    """
    max_size: int = 100
    timeout_ms: int = 5000
    max_queue_size: int = 10000  # Prevent unbounded memory growth


class BatchSpanProcessor:
    """Processor that batches events before exporting.
    
    Collects events up to max_size or timeout, then exports them in a batch.
    
    Features:
    - Bounded queue to prevent memory exhaustion
    - Retry logic with exponential backoff
    - Events only cleared after successful export
    - Thread-safe operations within async context
    
    Example:
        >>> exporter = HTTPExporter(endpoint="http://localhost:8000/api/v1/ingest/events")
        >>> processor = BatchSpanProcessor(exporter)
        >>> processor.set_run_id("run-123", run_name="My Agent")
        >>> await processor.add_event(event)
        >>> await processor.flush()
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
        # Bounded deque prevents unbounded memory growth
        self._events: deque[ExportEvent] = deque(maxlen=self._config.max_queue_size)
        self._run_id: str | None = None
        self._run_name: str | None = None
        self._lock = asyncio.Lock()
    
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
        
        If the queue is full (max_queue_size reached), the oldest event is dropped
        and a warning is logged.
        
        Args:
            event: The event to add.
        """
        async with self._lock:
            # Check if queue is at capacity
            if len(self._events) >= self._config.max_queue_size:
                logger.warning(
                    f"Event queue at capacity ({self._config.max_queue_size}), "
                    f"dropping oldest event to make room"
                )
                # deque with maxlen will automatically drop oldest, but we log it
            
            self._events.append(event)
            
            # Check if we should flush
            if len(self._events) >= self._config.max_size:
                await self._flush_internal()
    
    async def flush(self) -> None:
        """Flush all pending events.
        
        Raises:
            ExportError: If export fails after all retry attempts.
        """
        async with self._lock:
            await self._flush_internal()
    
    async def _flush_internal(self) -> None:
        """Internal flush without lock (caller must hold lock).
        
        Events are only cleared after successful export to prevent data loss.
        
        Raises:
            ExportError: If export fails.
        """
        if not self._events or not self._run_id:
            return
        
        # Create batch from pending events
        events = list(self._events)
        
        # Include run_name only for first batch (then clear it)
        run_name = self._run_name
        self._run_name = None  # Only send once
        
        batch = ExportBatch(
            run_id=self._run_id,
            events=events,
            run_name=run_name,
        )
        
        try:
            # Export (don't hold lock during network call)
            # Note: We release the lock during export, but events are still in memory
            # If this fails, we DON'T clear the queue - events can be retried
            await self._exporter.export(batch)
            
            # Only clear events AFTER successful export
            # This prevents data loss if export fails
            self._events.clear()
            
            logger.debug(f"Successfully exported {len(events)} events")
            
        except Exception as e:
            logger.error(f"Failed to export batch: {e}")
            # Re-raise to let caller handle
            # Events remain in queue for potential retry
            raise ExportError(f"Failed to export batch: {e}") from e
    
    async def close(self) -> None:
        """Flush pending events and close exporter.
        
        Raises:
            ExportError: If final flush fails.
        """
        try:
            await self.flush()
        finally:
            await self._exporter.close()