"""Node 2, parallel branch 2 -- DB2 vehicle sub-agent.

Queries Primo's DB2 for the corresponding vehicle/policy record. Composed
with `dmr_subagent` into `enrich_chain` (see agents/enrich/agent.py),
which runs both concurrently via LCEL `RunnableParallel`.

Assumption to confirm (open question, see README): this sub-agent never
calls live DB2 in the PoC -- `services.db2_service` is mocked, and the real
"no SQL during production hours" constraint does not apply here.
"""

from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableLambda

from agent_workflows.models.schemas import EnrichmentFinding, GateResult
from agent_workflows.services import db2_service
from agent_trace_sdk.langchain import leaf


async def _db2_lookup(gate: GateResult) -> EnrichmentFinding:
    return db2_service.lookup(gate.record)


db2_chain: Runnable[GateResult, EnrichmentFinding] = leaf(
    RunnableLambda(_db2_lookup), "db2_vehicle_subagent", span_type="tool_call"
)
