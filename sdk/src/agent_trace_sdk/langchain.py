"""LangChain / LangGraph callback bridge to Tracer.

`AgentTraceCallbackHandler` turns a subset of the chain-run callbacks a
`StateGraph` invocation fires into spans. Two kinds of chain run become a
span:

1. A graph node's own run. LangGraph tags every node's Pregel wrapper with
   ``graph:step:<n>`` and puts the node name in ``metadata["langgraph_node"]``.
   Per-node ``span_type`` comes from the metadata passed to
   ``StateGraph.add_node``.
2. A Runnable marked via ``leaf()`` — used for parallel sub-agents nested
   inside a node, where the node-level span alone would hide which branch
   produced what.

Every other chain run (``RunnableParallel`` / ``RunnableSequence`` wrappers,
etc.) is skipped so it does not duplicate a span one level up. Those runs
are still recorded in ``_parents`` so a real span's parent can be found by
walking up through skipped wrappers.
"""

from __future__ import annotations

import dataclasses
import inspect
from collections.abc import Callable, Sequence
from contextvars import Token
from functools import wraps
from typing import Any, TypeVar
from uuid import UUID

from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.runnables import Runnable
from pydash import filter_, merge, pick

from .context import add_event, get_current_span, reset_current_span, set_current_span
from .span import Span
from .tracer import Tracer

F = TypeVar("F", bound=Callable[..., Any])

# Tag bound (via `leaf`) on a parallel sub-agent Runnable so the callback
# handler can tell it apart from LangChain's own internal wrapper runs.
LEAF_TAG = "agent_trace:leaf"

# Metadata key carrying a leaf's span type. Deliberately not "span_type":
# graph-node metadata propagates into everything nested inside the node and
# wins the merge, so a leaf reusing that key would always read back the
# node's value instead of its own.
LEAF_SPAN_TYPE_KEY = "leaf_span_type"


def leaf(
    chain: Runnable[Any, Any],
    name: str,
    span_type: str = "step",
) -> Runnable[Any, Any]:
    """Mark `chain` as a traced leaf span named `name`.

    Only bind this on parallel sub-agents inside a node; single-Runnable
    nodes are already represented by their node-level span.

    `span_type` travels under its own key rather than reusing `span_type`,
    because a graph node's metadata propagates down and the inherited value
    wins the merge.
    """
    return chain.with_config(
        run_name=name,
        tags=[LEAF_TAG],
        metadata={LEAF_SPAN_TYPE_KEY: span_type},
    )


def trace_result(*fields: str) -> Callable[[F], F]:
    """Mark which return fields are this span's `result` for easy"""
    def decorator(fn: F) -> F:
        if inspect.iscoroutinefunction(fn):

            @wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                out = await fn(*args, **kwargs)
                _emit_result(out, fields)
                return out

            return async_wrapper  # type: ignore[return-value]

        @wraps(fn)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            out = fn(*args, **kwargs)
            _emit_result(out, fields)
            return out

        return sync_wrapper  # type: ignore[return-value]

    return decorator


def _emit_result(out: Any, fields: tuple[str, ...]) -> None:
    data = _to_jsonable(out)
    if not isinstance(data, dict):
        data = {"value": data}
    if fields:
        nested = filter_(data.values(), lambda v: isinstance(v, dict))
        data = pick(merge({}, data, *nested), *fields)
    if data:
        add_event("result", data)


def _to_jsonable(value: Any) -> Any:
    """Best-effort conversion of node input/output/error payloads to JSON."""
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        return {f.name: _to_jsonable(getattr(value, f.name)) for f in dataclasses.fields(value)}
    if isinstance(value, dict):
        return {str(k): _to_jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_to_jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


class AgentTraceCallbackHandler(AsyncCallbackHandler):
    """Bridges LangChain/LangGraph chain-run events to a specific Tracer.

    `run_inline` is True so start/end run in the same task as the node. That
    lets `set_current_span` be visible to node code (`add_event`) and lets
    `reset_current_span` see the token created at start.
    """

    run_inline = True

    def __init__(
        self,
        tracer: Tracer,
        *,
        attribute_keys: Sequence[str] = (),
    ) -> None:
        self._tracer = tracer
        self._attribute_keys = tuple(attribute_keys)
        self._parents: dict[UUID, UUID | None] = {}
        self._spans: dict[UUID, Span] = {}
        self._tokens: dict[UUID, Token[Span | None]] = {}

    @staticmethod
    def _graph_node_name(tags: list[str] | None, metadata: dict[str, Any] | None) -> str | None:
        if not tags or not any(t.startswith("graph:step:") for t in tags):
            return None
        return (metadata or {}).get("langgraph_node")

    def _resolve_parent(self, parent_run_id: UUID | None) -> Span | None:
        run_id = parent_run_id
        while run_id is not None:
            span = self._spans.get(run_id)
            if span is not None:
                return span
            run_id = self._parents.get(run_id)
        return get_current_span()

    def _release(self, run_id: UUID) -> Span | None:
        self._parents.pop(run_id, None)
        token = self._tokens.pop(run_id, None)
        if token is not None:
            try:
                reset_current_span(token)
            except ValueError:
                # Start/end can still land in different asyncio tasks for
                # some wrapper runs; do not skip span.complete() if so.
                pass
        return self._spans.pop(run_id, None)

    async def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: Any,
        *,
        run_id: UUID,
        parent_run_id: UUID | None = None,
        tags: list[str] | None = None,
        metadata: dict[str, Any] | None = None,
        name: str | None = None,
        **kwargs: Any,
    ) -> None:
        self._parents[run_id] = parent_run_id

        node_name = self._graph_node_name(tags, metadata)
        is_leaf = bool(tags and LEAF_TAG in tags)
        is_root = parent_run_id is None
        if not (node_name or is_leaf or is_root):
            return

        span_name = node_name or name or "run"
        default_span_type = "agent_run" if is_root else "step"
        meta = metadata or {}
        span_type = (
            meta.get(LEAF_SPAN_TYPE_KEY, default_span_type)
            if is_leaf
            else meta.get("span_type", default_span_type)
        )
        parent_span = self._resolve_parent(parent_run_id)

        attributes: dict[str, Any] = {}
        if is_root:
            for key in self._attribute_keys:
                if key in meta:
                    attributes[key] = meta[key]

        span = self._tracer.start_span(
            name=span_name,
            span_type=span_type,
            parent_id=parent_span.id if parent_span else None,
            attributes=attributes or None,
        )
        span.add_event("input", {"value": _to_jsonable(inputs)})
        self._spans[run_id] = span
        self._tokens[run_id] = set_current_span(span)

    async def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        span = self._release(run_id)
        if span is None:
            return
        span.add_event("output", {"value": _to_jsonable(outputs)})
        span.complete()

    async def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        span = self._release(run_id)
        if span is None:
            return
        span.add_event(
            "error",
            {"exception_type": type(error).__name__, "exception_message": str(error)},
        )
        span.complete()
