from __future__ import annotations

import asyncio
import logging
import warnings
from contextvars import Token
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from .context import (
    get_current_span,
    reset_current_run_id,
    reset_current_span,
    set_current_run_id,
    set_current_span,
)
from .domain.interfaces import ExportEvent, IEventExporter
from .exporter import HTTPExporter
from .processor import BatchConfig, BatchSpanProcessor
from .span import Span

logger = logging.getLogger(__name__)


def _utcnow() -> datetime:
    """Get current UTC time in a Python 3.12+ compatible way."""
    return datetime.now(timezone.utc)


class Tracer:
    """Main tracer for capturing AI agent traces.
    
    Usage:
        # Async context manager (preferred for CLI / asyncio.run)
        async with Tracer(name="my_agent") as span:
            span.set_attribute("model", "gpt-4")
            # ... agent logic ...
        
        # Sync context manager (no running event loop)
        with Tracer(name="my_agent") as span:
            ...
        
        # Decorator
        @trace_agent_run(name="my_agent")
        def my_agent():
            ...
    """
    
    _instance: Tracer | None = None
    
    def __init__(
        self,
        name: str,
        exporter: IEventExporter | None = None,
        batch_config: BatchConfig | None = None,
        endpoint: str | None = None,
        run_id: str | None = None,
    ) -> None:
        """Initialize tracer.
        
        Args:
            name: Name for the trace run.
            exporter: Exporter to use (defaults to HTTPExporter).
            batch_config: Batch processing configuration.
            endpoint: Endpoint URL for HTTP exporter.
            run_id: Optional run ID. Generated if omitted.
        """
        self._name = name
        self._run_id = run_id or str(uuid4())
        self._root_span: Span | None = None
        self._span_token: Token[Span | None] | None = None
        self._run_id_token: Token[str | None] | None = None
        self._pending: set[asyncio.Task[Any]] = set()
        self._closed = False
        
        if exporter is None:
            exporter = HTTPExporter(
                endpoint=endpoint or "http://localhost:8000/api/v1/ingest/events"
            )
        
        self._processor = BatchSpanProcessor(exporter, batch_config)
        self._processor.set_run_id(self._run_id, run_name=name)

    @property
    def run_id(self) -> str:
        """AgentTrace run ID this tracer exports under."""
        return self._run_id
    
    @classmethod
    def get_instance(cls) -> Tracer | None:
        """Get the global tracer instance.
        
        Returns:
            Global tracer instance or None.
        """
        return cls._instance
    
    @classmethod
    def set_instance(cls, tracer: Tracer | None) -> None:
        """Set the global tracer instance.
        
        Args:
            tracer: Tracer instance to set as global.
        """
        cls._instance = tracer
    
    def start_span(
        self,
        name: str,
        span_type: str = "step",
        parent_id: str | None = None,
        attributes: dict[str, Any] | None = None,
    ) -> Span:
        """Start a new span.
        
        Args:
            name: Human-readable name for the span.
            span_type: Type of span (agent_run, step, tool_call, llm_call).
            parent_id: Parent span ID, or None for root.
            attributes: Optional attributes to set before the span_start event.
            
        Returns:
            New Span instance.
        """
        if parent_id is None:
            current = get_current_span()
            if current is not None:
                parent_id = current.id
        
        span = Span.create(
            run_id=self._run_id,
            name=name,
            span_type=span_type,
            parent_id=parent_id,
            tracer=self,
        )
        if attributes:
            span.attributes.update(attributes)
        
        self._add_span_start_event(span)
        
        return span
    
    def _add_span_start_event(self, span: Span) -> None:
        """Add span_start event to processor and flush so the live graph can update."""
        event = ExportEvent(
            event_type="span_start",
            span_id=span.id,
            timestamp=span.started_at.isoformat(),
            data={
                "parent_id": span.parent_id,
                "name": span.name,
                "span_type": span.span_type,
                "attributes": span.attributes,
            },
        )
        self._schedule(self._emit(event, flush=True))
    
    def _end_span(self, span: Span) -> None:
        """Handle span end and flush so the live graph can update."""
        event = ExportEvent(
            event_type="span_end",
            span_id=span.id,
            timestamp=span.ended_at.isoformat() if span.ended_at else _utcnow().isoformat(),
            data={
                "attributes": span.attributes,
            },
        )
        self._schedule(self._emit(event, flush=True))
    
    def _add_event(
        self,
        span_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> None:
        """Add a custom event.
        
        Args:
            span_id: ID of the span the event belongs to.
            event_type: Type of event.
            payload: Event payload.
        """
        event = ExportEvent(
            event_type="span_event",
            span_id=span_id,
            timestamp=_utcnow().isoformat(),
            data={
                "event_type": event_type,
                "payload": payload,
            },
        )
        self._schedule(self._emit(event, flush=False))
    
    async def _emit(self, event: ExportEvent, *, flush: bool) -> None:
        await self._processor.add_event(event)
        if flush:
            await self._processor.flush()
    
    def _schedule(self, coro: Any) -> None:
        """Run an export coroutine without failing the agent run.
        
        On a running loop the work is tracked so `__aexit__` can await it.
        With no loop, the coroutine is run to completion immediately.
        """
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            self._run_sync(coro)
            return
        task = loop.create_task(self._run_logged(coro))
        self._pending.add(task)
        task.add_done_callback(self._pending.discard)
    
    async def _run_logged(self, coro: Any) -> None:
        try:
            await coro
        except Exception:
            logger.exception("Trace export failed")
    
    def _run_sync(self, coro: Any) -> None:
        async def _runner() -> None:
            try:
                await coro
            except Exception:
                logger.exception("Trace export failed")
        asyncio.run(_runner())
    
    def _activate(self) -> Span:
        Tracer.set_instance(self)
        self._run_id_token = set_current_run_id(self._run_id)
        self._root_span = self.start_span(
            name=self._name,
            span_type="agent_run",
        )
        self._span_token = set_current_span(self._root_span)
        return self._root_span
    
    def _deactivate(self, exc_type: Any, exc_val: Any) -> None:
        try:
            if self._root_span is not None:
                if exc_type is not None and not self._root_span._ended:
                    self._root_span.add_event("error", {
                        "exception_type": exc_type.__name__,
                        "exception_message": str(exc_val),
                    })
                self._root_span.complete()
        finally:
            if self._span_token is not None:
                reset_current_span(self._span_token)
                self._span_token = None
            if self._run_id_token is not None:
                reset_current_run_id(self._run_id_token)
                self._run_id_token = None
            if Tracer._instance is self:
                Tracer.set_instance(None)
    
    async def _shutdown(self) -> None:
        if self._closed:
            return
        self._closed = True
        current = asyncio.current_task()
        pending = [t for t in list(self._pending) if t is not current and not t.done()]
        if pending:
            await asyncio.gather(*pending, return_exceptions=True)
        try:
            await self._processor.close()
        except Exception:
            logger.exception("Trace flush/close failed")
    
    def __enter__(self) -> Span:
        """Enter tracer context.
        
        Starts a root span and sets it as current.
        
        Returns:
            Root span.
        """
        return self._activate()
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit tracer context.
        
        Ends the root span and flushes events. Prefer `async with` when an
        event loop is already running so flush is awaited before the loop
        closes.
        """
        self._deactivate(exc_type, exc_val)
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            asyncio.run(self._shutdown())
            return
        warnings.warn(
            "Tracer used as a sync context manager inside a running event loop; "
            "export may not finish. Use 'async with Tracer(...)'.",
            RuntimeWarning,
            stacklevel=2,
        )
        loop.create_task(self._shutdown())
    
    async def __aenter__(self) -> Span:
        """Enter tracer context and set the root as the current span."""
        return self._activate()
    
    async def __aexit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """End the root span, await SDK export tasks, then flush and close."""
        self._deactivate(exc_type, exc_val)
        await self._shutdown()
