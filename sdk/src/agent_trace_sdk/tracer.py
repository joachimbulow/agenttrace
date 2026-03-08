from __future__ import annotations

from typing import Any
from uuid import uuid4
from datetime import datetime, timezone
import asyncio

from .span import Span
from .exporter import HTTPExporter, ConsoleExporter
from .processor import BatchSpanProcessor, BatchConfig
from .context import set_current_run_id
from .domain.interfaces import ExportEvent


def _utcnow() -> datetime:
    """Get current UTC time in a Python 3.12+ compatible way."""
    return datetime.now(timezone.utc)


class Tracer:
    """Main tracer for capturing AI agent traces.
    
    Usage:
        # Context manager
        with Tracer(name="my_agent") as span:
            span.set_attribute("model", "gpt-4")
            # ... agent logic ...
        
        # Decorator
        @trace_agent_run(name="my_agent")
        def my_agent():
            ...
    """
    
    _instance: Tracer | None = None
    
    def __init__(
        self,
        name: str,
        exporter: HTTPExporter | ConsoleExporter | None = None,
        batch_config: BatchConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        """Initialize tracer.
        
        Args:
            name: Name for the trace run.
            exporter: Exporter to use (defaults to HTTPExporter).
            batch_config: Batch processing configuration.
            endpoint: Endpoint URL for HTTP exporter.
        """
        self._name = name
        self._run_id = str(uuid4())
        self._root_span: Span | None = None
        
        # Create exporter if not provided
        if exporter is None:
            exporter = HTTPExporter(endpoint=endpoint or "http://localhost:8000/api/v1/ingest/events")
        
        self._processor = BatchSpanProcessor(exporter, batch_config)
        # Pass run_name for first batch
        self._processor.set_run_id(self._run_id, run_name=name)
    
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
    ) -> Span:
        """Start a new span.
        
        Args:
            name: Human-readable name for the span.
            span_type: Type of span (agent_run, step, tool_call, llm_call).
            parent_id: Parent span ID, or None for root.
            
        Returns:
            New Span instance.
        """
        span = Span.create(
            run_id=self._run_id,
            name=name,
            span_type=span_type,
            parent_id=parent_id,
            tracer=self,
        )
        
        # Send span_start event
        self._add_span_start_event(span)
        
        return span
    
    def _add_span_start_event(self, span: Span) -> None:
        """Add span_start event to processor.
        
        Args:
            span: The span that was started.
        """
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
        self._run_async(self._processor.add_event(event))
    
    def _end_span(self, span: Span) -> None:
        """Handle span end.
        
        Args:
            span: The span that ended.
        """
        event = ExportEvent(
            event_type="span_end",
            span_id=span.id,
            timestamp=span.ended_at.isoformat() if span.ended_at else _utcnow().isoformat(),
            data={
                "attributes": span.attributes,
            },
        )
        self._run_async(self._processor.add_event(event))
    
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
        self._run_async(self._processor.add_event(event))
    
    def _run_async(self, coro: Any) -> None:
        """Run an async coroutine, handling the event loop.
        
        Args:
            coro: The coroutine to run.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(coro)
        except RuntimeError:
            # No running event loop - this is expected in sync context
            # We need to run in a new loop, but this blocks
            # For SDK use, this should typically be called from async context
            # or the user should handle the async properly
            import warnings
            warnings.warn(
                "SDK event submitted outside async context. "
                "Consider using async context manager or running in async function.",
                RuntimeWarning,
                stacklevel=3,
            )
            try:
                asyncio.run(coro)
            except RuntimeError:
                # Already in a loop (shouldn't happen, but be safe)
                pass
    
    def __enter__(self) -> Span:
        """Enter tracer context.
        
        Starts a root span and sets it as current.
        
        Returns:
            Root span.
        """
        # Set this as global instance
        Tracer.set_instance(self)
        
        # Set run ID in context
        set_current_run_id(self._run_id)
        
        # Start root span
        self._root_span = self.start_span(
            name=self._name,
            span_type="agent_run",
        )
        
        return self._root_span
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit tracer context.
        
        Ends the root span and flushes events.
        """
        # End root span
        if self._root_span:
            self._root_span.ended_at = _utcnow()
            self._end_span(self._root_span)
        
        # Flush and close processor
        self._run_async(self._processor.flush())
        
        # Clear global instance
        Tracer.set_instance(None)
        set_current_run_id(None)