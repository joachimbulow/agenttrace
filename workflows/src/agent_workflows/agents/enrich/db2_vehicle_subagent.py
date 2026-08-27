"""Node 2, parallel branch 2 -- DB2 vehicle sub-agent.

Queries Primo's DB2 for the corresponding vehicle/policy record. Runs
concurrently with `dmr_subagent` (see pipeline/orchestrator.py, which
gathers both).

Assumption to confirm (open question, see README): this sub-agent never
calls live DB2 in the PoC -- `services.db2_service` is mocked, and the real
"no SQL during production hours" constraint does not apply here.
"""

from __future__ import annotations

from agent_trace_sdk import trace_span

from agent_workflows.models.schemas import EnrichmentFinding, GateResult
from agent_workflows.services import db2_service


@trace_span(name="db2_vehicle_subagent", span_type="step")
async def db2_vehicle_subagent(gate: GateResult) -> EnrichmentFinding:
    return db2_service.lookup(gate.record)
