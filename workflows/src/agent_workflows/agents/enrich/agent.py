"""Node 2 -- Enrich: two parallel sub-agents, merged.

Runs `dmr_subagent` and `db2_vehicle_subagent` concurrently via LCEL
`RunnableParallel` (replaces the old `asyncio.gather` in the orchestrator
-- concurrency is now expressed by the agent's own composition, not by
hand-written control flow) and merges their findings into an
`EnrichmentResult`.
"""

from __future__ import annotations

from langchain_core.runnables import (
    Runnable,
    RunnableConfig,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

from agent_workflows.agents.enrich.db2_vehicle_subagent import db2_chain
from agent_workflows.agents.enrich.dmr_subagent import dmr_chain
from agent_workflows.models.schemas import EnrichmentResult, GateResult
from agent_workflows.pipeline.state import PipelineState


def _merge(parts: dict) -> EnrichmentResult:
    return EnrichmentResult(gate=parts["gate"], dmr=parts["dmr"], db2=parts["db2"])


enrich_chain: Runnable[GateResult, EnrichmentResult] = (
    RunnableParallel(dmr=dmr_chain, db2=db2_chain, gate=RunnablePassthrough())
    | RunnableLambda(_merge)
).with_config(run_name="enrich")


async def enrich_node(state: PipelineState, config: RunnableConfig) -> dict:
    assert state.gate is not None
    enrichment = await enrich_chain.ainvoke(state.gate, config)
    return {"enrichment": enrichment}
