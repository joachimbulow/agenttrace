"""Lifecycle tests for Tracer: current span, export flush, CLI asyncio.run."""
from __future__ import annotations

import asyncio
import warnings
from collections import Counter

import pytest

from agent_trace_sdk import Tracer, get_current_span
from agent_trace_sdk.domain.interfaces import ExportBatch, IEventExporter
from agent_trace_sdk.processor import BatchConfig


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


class _BoomExporter(IEventExporter):
    async def export(self, batch: ExportBatch) -> bool:
        raise RuntimeError("backend down")

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


def _events(exporter: _CapturingExporter):
    return [e for batch in exporter.batches for e in batch.events]


def test_sync_enter_sets_current_span_and_restores() -> None:
    exporter = _CapturingExporter()
    assert get_current_span() is None
    with Tracer(name="root", exporter=exporter) as span:
        assert get_current_span() is span
        assert span.name == "root"
        assert span.span_type == "agent_run"
    assert get_current_span() is None


def test_async_enter_sets_current_span_and_restores() -> None:
    exporter = _CapturingExporter()

    async def _run() -> None:
        assert get_current_span() is None
        async with Tracer(name="root", exporter=exporter) as span:
            assert get_current_span() is span
        assert get_current_span() is None

    asyncio.run(_run())


def test_one_span_end_per_start() -> None:
    exporter = _CapturingExporter()

    async def _run() -> None:
        async with Tracer(name="root", exporter=exporter) as root:
            tracer = Tracer.get_instance()
            assert tracer is not None
            with tracer.start_span("child"):
                pass
            child = tracer.start_span("manual")
            child.complete()
            child.complete()
            assert get_current_span() is root

    asyncio.run(_run())

    events = _events(exporter)
    starts = [e for e in events if e.event_type == "span_start"]
    ends = [e for e in events if e.event_type == "span_end"]
    assert len(starts) == 3
    assert {e.span_id for e in starts} == {e.span_id for e in ends}
    assert all(count == 1 for count in Counter(e.span_id for e in ends).values())


def test_child_span_parents_to_current_without_set_current_span() -> None:
    exporter = _CapturingExporter()

    async def _run() -> None:
        async with Tracer(name="root", exporter=exporter) as root:
            tracer = Tracer.get_instance()
            assert tracer is not None
            with tracer.start_span("child"):
                assert get_current_span() is not root
                assert get_current_span().name == "child"

    asyncio.run(_run())

    events = _events(exporter)
    starts = {e.span_id: e.data for e in events if e.event_type == "span_start"}
    root_id = next(sid for sid, d in starts.items() if d["name"] == "root")
    child = next(d for d in starts.values() if d["name"] == "child")
    assert child["parent_id"] == root_id


def test_async_with_awaits_flush_before_returning() -> None:
    exporter = _CapturingExporter()

    async def _run() -> None:
        async with Tracer(name="cli", exporter=exporter) as span:
            span.set_attribute("k", "v")
            span.add_event("output", {"ok": True})
        assert exporter.batches, "flush must complete before async with exits"

    asyncio.run(_run())
    types = {e.event_type for e in _events(exporter)}
    assert {"span_start", "span_end", "span_event"} <= types


def test_cli_asyncio_run_exports_without_gathering_all_tasks() -> None:
    """Mirrors workflows CLI: asyncio.run(async with Tracer(...))."""
    exporter = _CapturingExporter()
    hung: asyncio.Task[None] | None = None

    async def _run() -> None:
        nonlocal hung

        async def _hang() -> None:
            await asyncio.Event().wait()

        hung = asyncio.create_task(_hang())
        async with Tracer(name="cli", exporter=exporter):
            pass
        assert exporter.batches, "must not wait on unrelated tasks, but must still export"

    asyncio.run(_run())
    assert hung is not None
    # asyncio.run cancels leftover tasks; the hang must not have been awaited by Tracer
    types = {e.event_type for e in _events(exporter)}
    assert "span_start" in types
    assert "span_end" in types


def test_export_errors_do_not_fail_the_run() -> None:
    async def _run() -> str:
        async with Tracer(
            name="cli",
            exporter=_BoomExporter(),
            batch_config=BatchConfig(max_retries=0, timeout_ms=0),
        ):
            return "ok"

    assert asyncio.run(_run()) == "ok"


def test_sync_with_inside_running_loop_warns() -> None:
    async def _run() -> None:
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            with Tracer(name="sync", exporter=_CapturingExporter()):
                pass
        assert any(issubclass(w.category, RuntimeWarning) for w in caught)

    asyncio.run(_run())


def test_trace_agent_run_async_sets_current_span_and_flushes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from agent_trace_sdk.decorators import trace_agent_run

    injected = _CapturingExporter()
    original_init = Tracer.__init__

    def patched_init(
        self: Tracer,
        name: str,
        exporter: IEventExporter | None = None,
        batch_config: BatchConfig | None = None,
        endpoint: str | None = None,
    ) -> None:
        original_init(
            self,
            name,
            exporter=exporter or injected,
            batch_config=batch_config,
            endpoint=endpoint,
        )

    monkeypatch.setattr(Tracer, "__init__", patched_init)

    @trace_agent_run(name="decorated")
    async def agent() -> str:
        span = get_current_span()
        assert span is not None
        assert span.name == "decorated"
        return "ok"

    assert asyncio.run(agent()) == "ok"
    types = {e.event_type for e in _events(injected)}
    assert {"span_start", "span_end"} <= types
