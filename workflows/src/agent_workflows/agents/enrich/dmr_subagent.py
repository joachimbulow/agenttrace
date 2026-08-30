"""Node 2, parallel branch 1 -- DMR sub-agent.

Looks up the record against DMR reference data (vehicle/owner
details). Composed with `db2_vehicle_subagent` into `enrich_chain` (see
agents/enrich/agent.py), which runs both concurrently via LCEL
`RunnableParallel`.

Assumption to confirm (open question, see README): this sub-agent never
calls a live DMR system in the PoC -- `services.dmr_service` is mocked.
"""

from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableLambda

from agent_workflows.models.schemas import EnrichmentFinding, GateResult
from agent_workflows.services import dmr_service
from agent_trace_sdk.langchain import leaf


async def _dmr_lookup(gate: GateResult) -> EnrichmentFinding:
    return dmr_service.lookup(gate.record)


dmr_chain: Runnable[GateResult, EnrichmentFinding] = leaf(
    RunnableLambda(_dmr_lookup), "dmr_subagent", span_type="sub_agent"
)
