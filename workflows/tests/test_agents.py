from __future__ import annotations

import asyncio

from langchain_core.runnables import Runnable

from agent_workflows.agents.correct_validate.agent import correct_validate_chain
from agent_workflows.agents.determine_result.agent import determine_result_chain
from agent_workflows.agents.diagnose.agent import diagnose_chain
from agent_workflows.agents.enrich.agent import enrich_chain
from agent_workflows.agents.gate.agent import gate_chain
from agent_workflows.agents.judge.agent import judge_chain
from agent_workflows.agents.save_result.agent import save_result_chain
from agent_workflows.models.schemas import EnrichmentFinding, GateResult, RawRecord

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
    # This policy matches both reference tables (see services/dmr_service.py,
    # services/db2_service.py).
    assert result.dmr.status == "match"
    assert result.db2.status == "match"


def test_diagnose_chain_converges_three_paths() -> None:
    async def _run():
        record = RawRecord(policy_id="POL-1003", task_type="12_11", raw={"plate_number": "CD00000"})
        gate = GateResult(record=record, known=True, reason="ok")
        enrichment = await enrich_chain.ainvoke(gate)
        return enrichment, await diagnose_chain.ainvoke(enrichment)

    enrichment, diagnosis = asyncio.run(_run())

    assert diagnosis.enrichment is enrichment
    assert {p.path for p in diagnosis.proposals} == {"dmr", "db2", "rules"}
