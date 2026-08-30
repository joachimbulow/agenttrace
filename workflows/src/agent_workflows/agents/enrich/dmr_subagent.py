"""Node 2, parallel branch 1 -- DMR sub-agent.

Looks up the record against DMR reference data (vehicle/owner
details). Composed with `db2_vehicle_subagent` into `enrich_chain` (see
agents/enrich/agent.py), which runs both concurrently via LCEL
`RunnableParallel`.

Assumption to confirm (open question, see README): this sub-agent never
calls a live DMR system in the PoC -- `services.dmr_service` is mocked.
"""

from __future__ import annotations

import asyncio

from agent_trace_sdk import add_event
from agent_trace_sdk.langchain import leaf
from langchain_core.runnables import Runnable, RunnableLambda

from agent_workflows.models.schemas import EnrichmentFinding, GateResult
from agent_workflows.services import dmr_service


async def _dmr_lookup(gate: GateResult) -> EnrichmentFinding:
    await asyncio.sleep(5)  # TEMP: pause so the UI can be watched during test runs
    finding = dmr_service.lookup(gate.record)
    add_event("result", {"source": "dmr", "found": bool(finding.data)})
    return finding


dmr_chain: Runnable[GateResult, EnrichmentFinding] = leaf(
    RunnableLambda(_dmr_lookup), "dmr_subagent", span_type="sub_agent"
)
