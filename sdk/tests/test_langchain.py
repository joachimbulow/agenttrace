"""Unit tests for the optional LangChain callback bridge."""
from __future__ import annotations

import asyncio
from uuid import uuid4

import pytest

pytest.importorskip("langchain_core")

from langchain_core.runnables import RunnableLambda

from agent_trace_sdk import Tracer, add_event, get_current_span
from agent_trace_sdk.domain.interfaces import ExportBatch, IEventExporter
from agent_trace_sdk.langchain import (
    LEAF_SPAN_TYPE_KEY,
    LEAF_TAG,
    AgentTraceCallbackHandler,
    leaf,
)


class _CapturingExporter(IEventExporter):
    def __init__(self) -> None:
        self.batches: list[ExportBatch] = []

    async def export(self, batch: ExportBatch) -> bool:
        self.batches.append(batch)
        return True

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


def _events(exporter: _CapturingExporter):
    return [e for batch in exporter.batches for e in batch.events]


def test_handlers_export_only_to_their_own_tracer() -> None:
    """A handler bound to tracer A must not follow Tracer.get_instance() (B)."""

    async def _run() -> None:
        exp1 = _CapturingExporter()
        exp2 = _CapturingExporter()
        t1 = Tracer(name="t1", exporter=exp1)
        t2 = Tracer(name="t2", exporter=exp2)
        h1 = AgentTraceCallbackHandler(t1)
        h2 = AgentTraceCallbackHandler(t2)
        async with t1:
            async with t2:
                await h1.on_chain_start(
                    {},
                    {},
                    run_id=uuid4(),
                    parent_run_id=None,
                    name="from_t1",
                )
                await h2.on_chain_start(
                    {},
                    {},
                    run_id=uuid4(),
                    parent_run_id=None,
                    name="from_t2",
                )

        names1 = [e.data["name"] for e in _events(exp1) if e.event_type == "span_start"]
        names2 = [e.data["name"] for e in _events(exp2) if e.event_type == "span_start"]
        assert "from_t1" in names1
        assert "from_t2" not in names1
        assert "from_t2" in names2
        assert "from_t1" not in names2

    asyncio.run(_run())


def test_current_span_is_node_then_restored() -> None:
    async def _run() -> None:
        exporter = _CapturingExporter()
        tracer = Tracer(name="root", exporter=exporter)
        async with tracer as root:
            handler = AgentTraceCallbackHandler(tracer)
            run_id = uuid4()
            await handler.on_chain_start(
                {},
                {"in": 1},
                run_id=run_id,
                parent_run_id=None,
                tags=["graph:step:1"],
                metadata={"langgraph_node": "gate", "span_type": "step"},
                name="gate",
            )
            current = get_current_span()
            assert current is not None
            assert current.name == "gate"
            assert current is not root

            await handler.on_chain_end({"out": 2}, run_id=run_id)
            assert get_current_span() is root

    asyncio.run(_run())


def test_add_event_attaches_to_active_node_span() -> None:
    async def _run() -> None:
        exporter = _CapturingExporter()
        tracer = Tracer(name="root", exporter=exporter)
        async with tracer:
            handler = AgentTraceCallbackHandler(tracer)
            run_id = uuid4()
            await handler.on_chain_start(
                {},
                {"in": 1},
                run_id=run_id,
                parent_run_id=None,
                tags=["graph:step:1"],
                metadata={"langgraph_node": "gate"},
                name="gate",
            )
            node = get_current_span()
            assert node is not None
            add_event("note", {"ok": True})
            await handler.on_chain_end({"out": 2}, run_id=run_id)

        notes = [
            e
            for e in _events(exporter)
            if e.event_type == "span_event" and e.data.get("event_type") == "note"
        ]
        assert notes
        assert notes[0].span_id == node.id

    asyncio.run(_run())


def test_handler_runs_inline() -> None:
    exporter = _CapturingExporter()
    tracer = Tracer(name="root", exporter=exporter)
    handler = AgentTraceCallbackHandler(tracer)
    assert handler.run_inline is True


def test_leaf_binds_tag_and_span_type() -> None:
    bound = leaf(RunnableLambda(lambda x: x), "my_leaf", span_type="tool_call")
    config = bound.config
    assert config["run_name"] == "my_leaf"
    assert LEAF_TAG in config["tags"]
    assert config["metadata"][LEAF_SPAN_TYPE_KEY] == "tool_call"
    assert LEAF_TAG == "agent_trace:leaf"
