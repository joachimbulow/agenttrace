from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, TYPE_CHECKING
from uuid import uuid4
from contextvars import Token

from .context import set_current_span

if TYPE_CHECKING:
    from .tracer import Tracer


def _utcnow() -> datetime:
    """Get current UTC time in a Python 3.12+ compatible way.
    
    datetime.utcnow() is deprecated in Python 3.12+.
    """
    return datetime.now(timezone.utc)


@dataclass
class Span:
    """Represents a single span in a trace.
    
    A span is a unit of work within a trace, such as a single step,
    tool call, or LLM invocation.
    """
    
    id: str
    run_id: str
    name: str
    span_type: str
    started_at: datetime
    tracer: Tracer | None = None
    parent_id: str | None = None
    ended_at: datetime | None = None
    attributes: dict[str, Any] = field(default_factory=dict)
    _token: Token[Span | None] | None = field(default=None, repr=False)
    
    def __post_init__(self) -> None:
        """Validate span data."""
        if not self.id:
            raise ValueError("Span id cannot be empty")
        if not self.name:
            raise ValueError("Span name cannot be empty")
    
    @classmethod
    def create(
        cls,
        run_id: str,
        name: str,
        span_type: str = "step",
        parent_id: str | None = None,
        tracer: Tracer | None = None,
    ) -> Span:
        """Factory method to create a new span.
        
        Args:
            run_id: The run ID this span belongs to.
            name: Human-readable name for the span.
            span_type: Type of span (agent_run, step, tool_call, llm_call).
            parent_id: Parent span ID, or None for root.
            tracer: The tracer managing this span.
            
        Returns:
            New Span instance.
        """
        return cls(
            id=str(uuid4()),
            run_id=run_id,
            name=name,
            span_type=span_type,
            started_at=_utcnow(),
            parent_id=parent_id,
            tracer=tracer,
        )
    
    def set_attribute(self, key: str, value: Any) -> None:
        """Set an attribute on the span.
        
        Args:
            key: Attribute name.
            value: Attribute value (must be JSON serializable).
        """
        self.attributes[key] = value
    
    def add_event(self, event_type: str, payload: dict[str, Any] | None = None) -> None:
        """Add an event to the span.
        
        Args:
            event_type: Type of event (input, output, error).
            payload: Event payload.
        """
        if self.tracer:
            self.tracer._add_event(
                span_id=self.id,
                event_type=event_type,
                payload=payload or {},
            )
    
    def __enter__(self) -> Span:
        """Enter span context.
        
        Activates this span as the current span.
        
        Returns:
            Self.
        """
        # Save current span to restore later
        self._token = set_current_span(self)
        return self
    
    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        """Exit span context.
        
        Ends the span and restores the previous span.
        
        Args:
            exc_type: Exception type if raised, None otherwise.
            exc_val: Exception value if raised, None otherwise.
            exc_tb: Exception traceback if raised, None otherwise.
        """
        # End the span
        self.ended_at = _utcnow()
        
        # Add error event if exception occurred
        if exc_type is not None:
            self.add_event("error", {
                "exception_type": exc_type.__name__,
                "exception_message": str(exc_val),
            })
        
        # Export the span
        if self.tracer:
            self.tracer._end_span(self)
        
        # Restore previous span
        if self._token:
            from .context import _current_span
            _current_span.reset(self._token)
    
    def complete(self) -> None:
        """Mark the span as complete (alternative to context manager)."""
        self.ended_at = _utcnow()
        if self.tracer:
            self.tracer._end_span(self)