"""Batch processor for exporting trace events.

This module provides the BatchSpanProcessor which collects events and exports
them in batches for efficiency and reliability.
"""
from __future__ import annotations

import asyncio
import logging
from collections import deque
from dataclasses import dataclass

from .domain.interfaces import ExportBatch, ExportEvent, IEventExporter

logger = logging.getLogger(__name__)


@dataclass
class BatchConfig:
    """Configuration for batch processing.
    
    Attributes:
        max_size: Maximum batch size before forcing export.
        timeout_ms: Maximum time to wait before exporting a partial batch.
        max_queue_size: Maximum events to queue before dropping (memory protection).
        max_retries: Extra export attempts after the first failure. 0 means try once.
        retry_backoff_ms: Initial backoff between retries; doubles each attempt.
    """
    max_size: int = 100
    timeout_ms: int = 5000
    max_queue_size: int = 10000
    max_retries: int = 3
    retry_backoff_ms: int = 100


class BatchSpanProcessor:
    """Processor that batches events before exporting.
    
    Collects events up to max_size or timeout_ms, then exports them in a batch.
    
    Features:
    - Bounded queue to prevent memory exhaustion
    - Retry logic with exponential backoff
    - Events only cleared after successful export (restored on failure)
    - HTTP export does not hold the queue lock
    - Export failures are logged, never raised to the caller
    
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
        self._events: deque[ExportEvent] = deque(maxlen=self._config.max_queue_size)
        self._run_id: str | None = None
        self._run_name: str | None = None
        self._queue_lock = asyncio.Lock()
        self._flush_lock = asyncio.Lock()
        self._shutdown = asyncio.Event()
        self._timeout_task: asyncio.Task[None] | None = None
    
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
        and a warning is logged. Reaching max_size flushes immediately; otherwise
        a timeout flush is armed if one is not already running.
        
        Args:
            event: The event to add.
        """
        should_flush = False
        async with self._queue_lock:
            if len(self._events) >= self._config.max_queue_size:
                logger.warning(
                    "Event queue at capacity (%s), dropping oldest event to make room",
                    self._config.max_queue_size,
                )
            self._events.append(event)
            should_flush = len(self._events) >= self._config.max_size
            if not should_flush:
                self._arm_timer_unlocked()
        if should_flush:
            await self.flush()
    
    async def flush(self, *, drop_on_failure: bool = False) -> None:
        """Flush all pending events.
        
        Export errors are retried, then logged. They are never raised, so a
        down backend cannot fail the agent run.
        """
        async with self._flush_lock:
            batch = await self._take_batch()
            if batch is None:
                return
            ok = await self._export_with_retry(batch)
            if ok:
                logger.debug("Successfully exported %s events", len(batch.events))
                return
            if drop_on_failure:
                logger.error(
                    "Dropping %s events after failed export",
                    len(batch.events),
                )
                return
            async with self._queue_lock:
                for event in reversed(batch.events):
                    self._events.appendleft(event)
                if batch.run_name is not None and self._run_name is None:
                    self._run_name = batch.run_name
                self._arm_timer_unlocked()
    
    async def _take_batch(self) -> ExportBatch | None:
        """Snapshot and clear the queue. Does not hold the lock during export."""
        async with self._queue_lock:
            if not self._events or not self._run_id:
                return None
            events = list(self._events)
            self._events.clear()
            run_name = self._run_name
            self._run_name = None
            return ExportBatch(
                run_id=self._run_id,
                events=events,
                run_name=run_name,
            )
    
    async def _export_with_retry(self, batch: ExportBatch) -> bool:
        delay = self._config.retry_backoff_ms / 1000.0
        attempts = self._config.max_retries + 1
        last_error: BaseException | None = None
        for attempt in range(1, attempts + 1):
            try:
                await self._exporter.export(batch)
                return True
            except Exception as e:
                last_error = e
                logger.warning(
                    "Export attempt %s/%s failed: %s",
                    attempt,
                    attempts,
                    e,
                )
                if attempt < attempts and delay > 0:
                    await asyncio.sleep(delay)
                    delay *= 2
        logger.error("Failed to export batch after %s attempts: %s", attempts, last_error)
        return False
    
    def _arm_timer_unlocked(self) -> None:
        """Start a timeout flush if one is not already scheduled. Caller holds queue lock."""
        if self._shutdown.is_set():
            return
        if self._config.timeout_ms <= 0:
            return
        if self._timeout_task is not None and not self._timeout_task.done():
            return
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            return
        self._timeout_task = loop.create_task(self._on_timeout())
    
    async def _on_timeout(self) -> None:
        timeout_s = self._config.timeout_ms / 1000.0
        try:
            await asyncio.wait_for(self._shutdown.wait(), timeout=timeout_s)
            return
        except asyncio.TimeoutError:
            pass
        if self._shutdown.is_set():
            return
        await self.flush()
        async with self._queue_lock:
            if self._events and not self._shutdown.is_set():
                self._arm_timer_unlocked()
    
    async def close(self) -> None:
        """Flush pending events and close exporter.
        
        Export failures are logged and dropped rather than raised.
        """
        self._shutdown.set()
        task = self._timeout_task
        self._timeout_task = None
        if task is not None:
            try:
                if not task.done() and task.get_loop() is asyncio.get_running_loop():
                    await task
            except (RuntimeError, asyncio.CancelledError):
                pass
        try:
            await self.flush(drop_on_failure=True)
        except Exception:
            logger.exception("Final flush failed")
        try:
            await self._exporter.close()
        except Exception:
            logger.exception("Exporter close failed")
