from __future__ import annotations

from contextvars import ContextVar, Token
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .span import Span

# Context variables for tracing
_current_span: ContextVar[Span | None] = ContextVar("current_span", default=None)
_current_run_id: ContextVar[str | None] = ContextVar("current_run_id", default=None)


def get_current_span() -> Span | None:
    """Get the current active span from context.
    
    Returns:
        Current span or None if no span is active.
    """
    return _current_span.get()


def set_current_span(span: Span | None) -> Token[Span | None]:
    """Set the current active span in context.
    
    Args:
        span: Span to set as current, or None to clear.
        
    Returns:
        Token that can be used to reset to previous value.
    """
    return _current_span.set(span)


def get_current_run_id() -> str | None:
    """Get the current run ID from context.
    
    Returns:
        Current run ID or None if no run is active.
    """
    return _current_run_id.get()


def set_current_run_id(run_id: str | None) -> Token[str | None]:
    """Set the current run ID in context.
    
    Args:
        run_id: Run ID to set as current, or None to clear.
        
    Returns:
        Token that can be used to reset to previous value.
    """
    return _current_run_id.set(run_id)