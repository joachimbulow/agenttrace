"""Tests for BatchSpanProcessor: timeout, retry, and lock release during export."""
from __future__ import annotations

import asyncio

from agent_trace_sdk.domain.interfaces import ExportBatch, ExportEvent, IEventExporter
from agent_trace_sdk.processor import BatchConfig, BatchSpanProcessor


def _event(span_id: str = "s1", event_type: str = "span_event") -> ExportEvent:
    return ExportEvent(
        event_type=event_type,
        span_id=span_id,
        timestamp="2024-01-01T00:00:00Z",
        data={"event_type": "input", "payload": {}} if event_type == "span_event" else {"name": "t"},
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


class _SlowExporter(IEventExporter):
    def __init__(self) -> None:
        self.in_export = asyncio.Event()
        self.release = asyncio.Event()
        self.batches: list[ExportBatch] = []

    async def export(self, batch: ExportBatch) -> bool:
        self.in_export.set()
        await self.release.wait()
        self.batches.append(batch)
        return True

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


class _FlakyExporter(IEventExporter):
    def __init__(self, fail_times: int) -> None:
        self.calls = 0
        self.fail_times = fail_times
        self.batches: list[ExportBatch] = []

    async def export(self, batch: ExportBatch) -> bool:
        self.calls += 1
        if self.calls <= self.fail_times:
            raise RuntimeError("down")
        self.batches.append(batch)
        return True

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


def test_timeout_ms_flushes_partial_batch() -> None:
    async def _run() -> None:
        exporter = _CapturingExporter()
        processor = BatchSpanProcessor(
            exporter,
            BatchConfig(max_size=100, timeout_ms=50, max_retries=0),
        )
        processor.set_run_id("run-1", run_name="t")
        await processor.add_event(_event())
        assert exporter.batches == []
        await asyncio.sleep(0.2)
        assert len(exporter.batches) == 1
        assert len(exporter.batches[0].events) == 1
        await processor.close()

    asyncio.run(_run())


def test_retry_then_success() -> None:
    async def _run() -> None:
        exporter = _FlakyExporter(fail_times=2)
        processor = BatchSpanProcessor(
            exporter,
            BatchConfig(max_size=1, timeout_ms=0, max_retries=3, retry_backoff_ms=0),
        )
        processor.set_run_id("run-1")
        await processor.add_event(_event(event_type="span_start"))
        assert exporter.calls == 3
        assert len(exporter.batches) == 1
        await processor.close()

    asyncio.run(_run())


def test_retry_exhausted_does_not_raise() -> None:
    async def _run() -> None:
        exporter = _FlakyExporter(fail_times=99)
        processor = BatchSpanProcessor(
            exporter,
            BatchConfig(max_size=1, timeout_ms=0, max_retries=1, retry_backoff_ms=0),
        )
        processor.set_run_id("run-1")
        await processor.add_event(_event(event_type="span_start"))
        await processor.close()
        assert exporter.calls >= 2
        assert exporter.batches == []

    asyncio.run(_run())


def test_queue_lock_not_held_during_export() -> None:
    async def _run() -> None:
        exporter = _SlowExporter()
        processor = BatchSpanProcessor(
            exporter,
            BatchConfig(max_size=100, timeout_ms=0, max_retries=0),
        )
        processor.set_run_id("run-1")
        await processor.add_event(_event("s1"))
        flush_task = asyncio.create_task(processor.flush())
        await asyncio.wait_for(exporter.in_export.wait(), timeout=1)
        await asyncio.wait_for(processor.add_event(_event("s2")), timeout=0.2)
        exporter.release.set()
        await flush_task
        await processor.flush()
        await processor.close()
        exported_ids = [e.span_id for b in exporter.batches for e in b.events]
        assert "s1" in exported_ids
        assert "s2" in exported_ids

    asyncio.run(_run())
