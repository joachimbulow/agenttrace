"""Node 2, parallel branch 1 -- DMR sub-agent.

Looks up/matches the record against DMR reference data (vehicle/owner
details). Runs concurrently with `db2_vehicle_subagent` (see
pipeline/orchestrator.py, which gathers both).

Assumption to confirm (open question, see README): this sub-agent never
calls a live DMR system in the PoC -- `services.dmr_service` is mocked.
"""

from __future__ import annotations

from agent_trace_sdk import trace_span

from agent_workflows.models.schemas import EnrichmentFinding, GateResult
from agent_workflows.services import dmr_service


@trace_span(name="dmr_subagent", span_type="step")
async def dmr_subagent(gate: GateResult) -> EnrichmentFinding:
    return dmr_service.lookup(gate.record)
