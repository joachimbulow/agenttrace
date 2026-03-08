from __future__ import annotations
from typing import Callable, TypeVar, ParamSpec
from functools import wraps
import asyncio

from .tracer import Tracer
from .span import Span
from .context import get_current_span

P = ParamSpec("P")
R = TypeVar("R")


def trace_agent_run(
    name: str | None = None,
    endpoint: str | None = None,
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace a function as an agent run.
    
    Usage:
        @trace_agent_run(name="my_agent")
        def my_agent_function(input: str) -> str:
            # ... agent logic ...
            return result
        
        @trace_agent_run()  # Uses function name
        async def my_async_agent(input: str) -> str:
            # ... async agent logic ...
            return result
    
    Args:
        name: Name for the trace run (defaults to function name).
        endpoint: Endpoint URL for the exporter.
        
    Returns:
        Decorated function.
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        run_name = name or func.__name__
        
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Sync wrapper for traced function."""
            with Tracer(name=run_name, endpoint=endpoint) as span:
                # Store span in kwargs if function accepts it
                if "trace_span" in func.__code__.co_varnames:
                    kwargs["trace_span"] = span
                
                result = func(*args, **kwargs)
                return result
        
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Async wrapper for traced function."""
            with Tracer(name=run_name, endpoint=endpoint) as span:
                # Store span in kwargs if function accepts it
                if "trace_span" in func.__code__.co_varnames:
                    kwargs["trace_span"] = span
                
                if asyncio.iscoroutinefunction(func):
                    result = await func(*args, **kwargs)
                else:
                    result = func(*args, **kwargs)
                
                return result
        
        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator


def trace_span(
    name: str,
    span_type: str = "step",
) -> Callable[[Callable[P, R]], Callable[P, R]]:
    """Decorator to trace a function as a span within a run.
    
    Must be used within a @trace_agent_run decorated function.
    
    Usage:
        @trace_agent_run(name="my_agent")
        def my_agent():
            @trace_span(name="step1", span_type="step")
            def step1():
                ...
            
            @trace_span(name="tool_call", span_type="tool_call")
            def use_tool():
                ...
    
    Args:
        name: Name for the span.
        span_type: Type of span (step, tool_call, llm_call).
        
    Returns:
        Decorated function.
    """
    def decorator(func: Callable[P, R]) -> Callable[P, R]:
        @wraps(func)
        def sync_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Sync wrapper for traced span."""
            tracer = Tracer.get_instance()
            if tracer is None:
                # No active tracer, just call the function
                return func(*args, **kwargs)
            
            parent = get_current_span()
            parent_id = parent.id if parent else None
            
            with tracer.start_span(name=name, span_type=span_type, parent_id=parent_id):
                return func(*args, **kwargs)
        
        @wraps(func)
        async def async_wrapper(*args: P.args, **kwargs: P.kwargs) -> R:
            """Async wrapper for traced span."""
            tracer = Tracer.get_instance()
            if tracer is None:
                # No active tracer, just call the function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
            
            parent = get_current_span()
            parent_id = parent.id if parent else None
            
            with tracer.start_span(name=name, span_type=span_type, parent_id=parent_id):
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)
        
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore
    
    return decorator