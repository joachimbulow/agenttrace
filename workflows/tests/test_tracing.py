"""Verifies the LangChain callback bridge (agent_trace_sdk.langchain)
produces a correctly-nested trace tree when the pipeline runs -- this is
the behavior pipeline/orchestrator.py's refactor to a LangGraph
`StateGraph` exists to enable, so it's worth testing directly rather than
only indirectly through `PipelineOutcome` assertions.
"""

from __future__ import annotations

import asyncio
from collections import Counter
from pathlib import Path

from agent_trace_sdk import Span, Tracer
from agent_trace_sdk.domain.interfaces import ExportBatch, ExportEvent, IEventExporter

from agent_workflows.models.schemas import PipelineOutcome
from agent_workflows.pipeline.orchestrator import run_pipeline

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_CSV = DATA_DIR / "sample_extract.csv"


class _CapturingExporter(IEventExporter):
    """In-memory stand-in for HTTPExporter so tests don't need a backend."""

    def __init__(self) -> None:
        self.batches: list[ExportBatch] = []

    async def export(self, batch: ExportBatch) -> bool:
        self.batches.append(batch)
        return True

    async def flush(self) -> None:
        pass

    async def close(self) -> None:
        pass


def _run_traced(
    csv_path: str,
) -> tuple[list[PipelineOutcome], list[ExportEvent], Span]:
    async def _run():
        exporter = _CapturingExporter()
        tracer = Tracer(name="test_run", exporter=exporter)
        async with tracer as root_span:
            outcomes = await run_pipeline(csv_path, tracer=tracer)
        return outcomes, exporter, root_span

    outcomes, exporter, root_span = asyncio.run(_run())
    events = [e for batch in exporter.batches for e in batch.events]
    return outcomes, events, root_span


def test_pipeline_run_produces_correctly_nested_spans() -> None:
    outcomes, events, root_span = _run_traced(str(SAMPLE_CSV))

    assert all(o.record_id for o in outcomes)
    assert all(o.run_id == root_span.run_id for o in outcomes)

    starts = {e.span_id: e.data for e in events if e.event_type == "span_start"}
    end_counts = Counter(e.span_id for e in events if e.event_type == "span_end")

    # Every started span ends exactly once -- no orphaned in-flight spans and
    # no duplicate span_end exports for the same span.
    assert set(starts) == set(end_counts)
    assert all(count == 1 for count in end_counts.values())

    names = [d["name"] for d in starts.values()]
    # One root-level record span per CSV record, correctly parented under the
    # pipeline's root span (Tracer.__enter__/__aenter__ pushes the root as
    # the ambient current span).
    record_spans = [
        span_id for span_id, d in starts.items() if d["name"].startswith("primo_record[")
    ]
    assert len(record_spans) == 7
    for span_id in record_spans:
        assert starts[span_id]["parent_id"] == root_span.id
        attrs = starts[span_id].get("attributes") or {}
        assert attrs.get("record_id")
        assert attrs.get("policy_id")

    # The full expected node/sub-agent span vocabulary shows up somewhere
    # across the 7 records (mix of known/unknown, correct_validate/save_result).
    expected_names = {
        "gate",
        "reject",
        "enrich",
        "dmr_subagent",
        "db2_vehicle_subagent",
        "diagnose",
        "diagnose_dmr_path",
        "diagnose_db2_path",
        "diagnose_rules_path",
        "judge",
        "determine_result",
        "correct_validate",
        "save_result",
    }
    assert expected_names.issubset(set(names))


def test_enrich_sub_agent_spans_nest_under_enrich_not_flat() -> None:
    _, events, _ = _run_traced(str(SAMPLE_CSV))
    starts = {e.span_id: e.data for e in events if e.event_type == "span_start"}

    enrich_span_ids = {sid for sid, d in starts.items() if d["name"] == "enrich"}
    dmr_starts = [d for d in starts.values() if d["name"] == "dmr_subagent"]
    db2_starts = [d for d in starts.values() if d["name"] == "db2_vehicle_subagent"]

    assert dmr_starts and db2_starts
    for d in dmr_starts + db2_starts:
        assert d["parent_id"] in enrich_span_ids


def test_diagnose_sub_paths_nest_under_diagnose() -> None:
    _, events, _ = _run_traced(str(SAMPLE_CSV))
    starts = {e.span_id: e.data for e in events if e.event_type == "span_start"}

    diagnose_span_ids = {sid for sid, d in starts.items() if d["name"] == "diagnose"}
    for path_name in ("diagnose_dmr_path", "diagnose_db2_path", "diagnose_rules_path"):
        path_starts = [d for d in starts.values() if d["name"] == path_name]
        assert path_starts
        for d in path_starts:
            assert d["parent_id"] in diagnose_span_ids


def test_judge_span_type_is_llm_call_others_are_step() -> None:
    _, events, _ = _run_traced(str(SAMPLE_CSV))
    starts = [e.data for e in events if e.event_type == "span_start"]

    judge_types = {d["span_type"] for d in starts if d["name"] == "judge"}
    assert judge_types == {"llm_call"}

    gate_types = {d["span_type"] for d in starts if d["name"] == "gate"}
    assert gate_types == {"step"}


def test_spans_carry_input_and_output_events() -> None:
    _, events, _ = _run_traced(str(SAMPLE_CSV))
    starts = {e.span_id: e.data for e in events if e.event_type == "span_start"}
    gate_span_ids = {sid for sid, d in starts.items() if d["name"] == "gate"}

    span_events = [e for e in events if e.event_type == "span_event" and e.span_id in gate_span_ids]
    event_types = {e.data["event_type"] for e in span_events}
    assert {"input", "output"}.issubset(event_types)
