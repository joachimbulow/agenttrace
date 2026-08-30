from __future__ import annotations

import asyncio

from agent_trace_sdk import Tracer
from agent_trace_sdk.domain.interfaces import ExportBatch, IEventExporter
from langchain_core.runnables import Runnable

from agent_workflows.agents.correct_validate.agent import correct_validate_chain
from agent_workflows.agents.determine_result.agent import determine_result_chain
from agent_workflows.agents.diagnose.agent import diagnose_chain
from agent_workflows.agents.enrich.agent import enrich_chain
from agent_workflows.agents.gate.agent import gate_chain
from agent_workflows.agents.judge.agent import judge_chain
from agent_workflows.agents.save_result.agent import save_result_chain
from agent_workflows.models.schemas import EnrichmentFinding, GateResult, RawRecord


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

ALL_CHAINS = [
    gate_chain,
    enrich_chain,
    diagnose_chain,
    judge_chain,
    determine_result_chain,
    correct_validate_chain,
    save_result_chain,
]


def test_every_agent_is_a_langchain_runnable() -> None:
    for chain in ALL_CHAINS:
        assert isinstance(chain, Runnable)


def test_enrich_chain_runs_dmr_and_db2_concurrently_and_merges() -> None:
    # enrich_chain's sub-agents are async (they call an async lookup), so
    # like the rest of the pipeline it only supports `ainvoke`, not the
    # sync `invoke` -- see agents/enrich/dmr_subagent.py.
    async def _run():
        record = RawRecord(
            policy_id="POL-1001",
            task_type="12_11",
            raw={
                "plate_number": "AB12345",
                "owner_name": "Anna Larsen",
                "vehicle_make": "Volvo",
                "vehicle_model": "V60",
            },
        )
        gate = GateResult(record=record, known=True, reason="ok")
        return gate, await enrich_chain.ainvoke(gate)

    gate, result = asyncio.run(_run())

    assert result.gate is gate
    assert isinstance(result.dmr, EnrichmentFinding)
    assert isinstance(result.db2, EnrichmentFinding)
    assert result.dmr.source == "dmr"
    assert result.db2.source == "db2"
    # Enrichment looks up; it does not conclude match/mismatch.
    assert result.dmr.data
    assert result.db2.data


def test_diagnose_chain_converges_three_paths() -> None:
    async def _run():
        record = RawRecord(
            policy_id="POL-1003",
            task_type="12_11",
            raw={
                "plate_number": "CD44444",
                "owner_name": "Cecilie Holm",
                "vehicle_make": "Toyota",
                "vehicle_model": "Corolla",
            },
        )
        gate = GateResult(record=record, known=True, reason="ok")
        enrichment = await enrich_chain.ainvoke(gate)
        return enrichment, await diagnose_chain.ainvoke(enrichment)

    enrichment, diagnosis = asyncio.run(_run())

    assert diagnosis.enrichment is enrichment
    assert {p.path for p in diagnosis.proposals} == {"dmr", "db2", "rules"}
    by_path = {p.path: p for p in diagnosis.proposals}
    # POL-1003: CSV plate matches DMR (CD44444), not DB2 (CD00000).
    assert by_path["dmr"].status == "match"
    assert by_path["db2"].status == "mismatch"


def test_gate_emits_result_on_active_span() -> None:
    async def _run():
        exporter = _CapturingExporter()
        tracer = Tracer(name="gate_result", exporter=exporter)
        async with tracer:
            with tracer.start_span("gate", span_type="step"):
                return gate_chain.invoke(
                    RawRecord(policy_id="POL-1001", task_type="12_11")
                ), exporter

    result, exporter = asyncio.run(_run())
    assert result is not None
    assert result.known is True
    results = [
        event
        for batch in exporter.batches
        for event in batch.events
        if event.event_type == "span_event" and event.data.get("event_type") == "result"
    ]
    assert results
    assert results[0].data["payload"] == {"known": True, "task_type": "12_11"}
