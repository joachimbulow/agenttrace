"""LangChain callback bridge to the agent_trace_sdk Tracer.

Replaces the old per-function `@trace_span` decorator: node/agent timing,
input, output and errors are now captured via LangChain's own callback
system (`AsyncCallbackHandler`) instead of ad hoc wrapping, so any
LangChain-aware tool (this bridge, LangSmith, etc.) can observe the same
run events.

`AgentTraceCallbackHandler` turns a subset of the many LangChain "chain
run" callbacks a `StateGraph` invocation fires into `agent_trace_sdk`
spans. Two kinds of chain run become a span:

1. A graph node's own run. LangGraph internally tags every node's Pregel
   wrapper run with a `"graph:step:<n>"` tag and puts the node's name in
   `metadata["langgraph_node"]` -- see the empirically-verified shape in
   pipeline/orchestrator.py's module docstring. This is what produces the
   gate / enrich / diagnose / judge / determine_result /
   correct_validate|save_result spans. Per-node `span_type` (e.g. judge's
   "llm_call") comes from the `metadata` passed to `StateGraph.add_node`.
2. A Runnable explicitly marked via `leaf()` below -- used only for the
   parallel sub-agents nested inside a node (the two enrich sub-agents,
   the three diagnose paths) where the node-level span alone would hide
   which branch produced what.

Every other chain run LangChain/LangGraph creates internally
(`RunnableParallel`/`RunnableSequence`/`RunnablePassthrough` wrappers, the
graph's own outer per-record run, ...) is deliberately not turned into a
span -- it would just duplicate a span that already exists one level up.
Those runs are still recorded in `_parents` so a real span's parent can be
found by walking up through any number of skipped wrapper runs.
"""

from __future__ import annotations

import dataclasses
import os
from typing import Any
from uuid import UUID

from agent_trace_sdk import Span, Tracer, get_current_span
from langchain_core.callbacks.base import AsyncCallbackHandler
from langchain_core.runnables import Runnable

DEFAULT_INGEST_ENDPOINT = "http://localhost:8000/api/v1/ingest/events"

# Tag bound (via `leaf`) on a parallel sub-agent Runnable so the callback
# handler can tell it apart from LangChain's own internal wrapper runs,
# which never carry this tag.
LEAF_TAG = "agent_workflows:leaf"

# Metadata key carrying a leaf's span type. Deliberately not "span_type":
# graph-node metadata propagates into everything nested inside the node and
# wins the merge, so a leaf reusing that key would always read back the
# node's value instead of its own.
LEAF_SPAN_TYPE_KEY = "leaf_span_type"


def ingest_endpoint() -> str:
    return os.environ.get("AGENTTRACE_ENDPOINT", DEFAULT_INGEST_ENDPOINT)


def leaf(
    chain: Runnable[Any, Any],
    name: str,
    span_type: str = "step",
) -> Runnable[Any, Any]:
    """Mark `chain` as a traced leaf span named `name`.

    Only bind this on the parallel sub-agents inside a node (dmr/db2
    enrich sub-agents, the three diagnose paths); single-Runnable nodes
    are already fully represented by their own node-level span (see
    `AgentTraceCallbackHandler`), so tagging them here would just create a
    redundant nested span with the same name.

    `span_type` drives how the span is rendered. Pass "tool_call" for a
    sub-agent whose work is a call out to another system, so it is
    distinguishable from in-process reasoning steps.

    It travels under its own key rather than reusing `span_type`, because
    a graph node's metadata propagates down to everything inside it and
    the inherited value wins the merge: a leaf setting `span_type` inside
    a node declared `metadata={"span_type": "step"}` would silently keep
    the node's value.
    """
    return chain.with_config(
        run_name=name,
        tags=[LEAF_TAG],
        metadata={LEAF_SPAN_TYPE_KEY: span_type},
    )


def _to_jsonable(value: Any) -> Any:
    """Best-effort conversion of arbitrary node input/output/error payloads
    into a JSON-safe shape for the HTTP exporter (dataclasses -> dicts,
    containers recursed into, anything else -> str)."""
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
    """Bridges LangChain/LangGraph chain-run events to our custom agent_trace_sdk spans."""
    def __init__(self) -> None:
        self._parents: dict[UUID, UUID | None] = {}
        self._spans: dict[UUID, Span] = {}

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
        """Bound to a langchain start."""
        self._parents[run_id] = parent_run_id

        tracer = Tracer.get_instance()
        if tracer is None:
            return

        node_name = self._graph_node_name(tags, metadata)
        is_leaf = bool(tags and LEAF_TAG in tags)
        is_root = parent_run_id is None
        if not (node_name or is_leaf or is_root):
            return

        span_name = node_name or name or "run"
        default_span_type = "agent_run" if is_root else "step"
        meta = metadata or {}
        # A leaf reads its own key; anything else reads the node's. See
        # LEAF_SPAN_TYPE_KEY for why they cannot share one.
        span_type = (
            meta.get(LEAF_SPAN_TYPE_KEY, default_span_type)
            if is_leaf
            else meta.get("span_type", default_span_type)
        )
        parent_span = self._resolve_parent(parent_run_id)

        attributes: dict[str, Any] = {}
        if is_root:
            meta = metadata or {}
            if "record_id" in meta:
                attributes["record_id"] = meta["record_id"]
            if "policy_id" in meta:
                attributes["policy_id"] = meta["policy_id"]

        span = tracer.start_span(
            name=span_name,
            span_type=span_type,
            parent_id=parent_span.id if parent_span else None,
            attributes=attributes or None,
        )
        span.add_event("input", {"value": _to_jsonable(inputs)})
        self._spans[run_id] = span

    async def on_chain_end(self, outputs: Any, *, run_id: UUID, **kwargs: Any) -> None:
        self._parents.pop(run_id, None)
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.add_event("output", {"value": _to_jsonable(outputs)})
        span.complete()

    async def on_chain_error(self, error: BaseException, *, run_id: UUID, **kwargs: Any) -> None:
        self._parents.pop(run_id, None)
        span = self._spans.pop(run_id, None)
        if span is None:
            return
        span.add_event(
            "error",
            {"exception_type": type(error).__name__, "exception_message": str(error)},
        )
        span.complete()


agent_trace_callback_handler = AgentTraceCallbackHandler()
