"""Control-flow ONLY -- wires the 6 nodes together, no business logic.

This module's only job is to make the shape of the graph legible: which
nodes run in sequence, which run concurrently, and where the branch
happens. All the actual "what does this mean" logic lives in
`agent_workflows.agents.*` and `agent_workflows.services.*`.

Graph shape:

    gate
      |-- known --> enrich (dmr_subagent + db2_vehicle_subagent, parallel)
      |               --> diagnose (dmr / db2 / rules paths, parallel, converge)
      |                     --> judge (mocked LLM-as-judge)
      |                           --> determine_result (threshold)
      |                                 |-- correct_validate (Path A)
      |                                 |-- save_result      (Path B)
      |-- unknown --> early-exit outcome, no further nodes run

================================================================================
KNOWN OPEN QUESTIONS / ASSUMPTIONS -- carried forward from the source spec.
Do NOT resolve these silently; confirm with the domain/source team. See also
workflows/README.md, which repeats this list for visibility.
================================================================================

1. "Diagnose/Propose: three parallel paths" -- unconfirmed whether this
   really means DMR + DB2 + rules, or something else. The rules-based third
   path in `agents/diagnose/agent.py` is an assumption made to fill out the
   count, not a confirmed requirement.

2. The real Primo CSV extract schema (columns) is not finalized.
   `services/csv_loader.py` is deliberately schema-tolerant (only requires
   `policy_id` and `task_type`) -- adjust once the real schema is known.

3. `agents/determine_result/agent.py`'s CONFIDENCE_THRESHOLD (0.75) is a
   placeholder, not calibrated against real data or SME input.

See also `agents/judge/agent.py` for a fourth, narrower implementation
choice about how "conflict" is defined between the DMR and DB2 paths.
================================================================================
"""

from __future__ import annotations

import asyncio

from agent_workflows.agents.correct_validate.agent import correct_validate_node
from agent_workflows.agents.determine_result.agent import determine_result_node
from agent_workflows.agents.diagnose.agent import diagnose_node
from agent_workflows.agents.enrich.db2_vehicle_subagent import db2_vehicle_subagent
from agent_workflows.agents.enrich.dmr_subagent import dmr_subagent
from agent_workflows.agents.gate.agent import gate_node
from agent_workflows.agents.judge.agent import judge_node
from agent_workflows.agents.save_result.agent import save_result_node
from agent_workflows.models.schemas import EnrichmentResult, PipelineOutcome, RawRecord
from agent_workflows.services.csv_loader import load_records


async def _run_record(record: RawRecord) -> PipelineOutcome:
    """Run one record through the full 6-node pipeline."""
    gate = gate_node(record)

    if not gate.known:
        return PipelineOutcome(
            policy_id=record.policy_id,
            task_type=record.task_type,
            known=False,
            branch=None,
            confidence=None,
            summary=gate.reason,
        )

    # Node 2 -- two parallel enrichment sub-agents.
    dmr_finding, db2_finding = await asyncio.gather(
        dmr_subagent(gate),
        db2_vehicle_subagent(gate),
    )
    enrichment = EnrichmentResult(gate=gate, dmr=dmr_finding, db2=db2_finding)

    # Node 3 -- three parallel diagnostic paths, converge.
    diagnosis = await diagnose_node(enrichment)

    # Node 4 -- judge (mocked LLM-as-judge).
    verdict = judge_node(diagnosis)

    # Node 5 -- threshold the verdict into a branch.
    decision = determine_result_node(verdict)

    # Node 6 -- branch.
    if decision.branch == "correct_validate":
        return correct_validate_node(decision)
    return save_result_node(decision)


async def run_pipeline(csv_path: str) -> list[PipelineOutcome]:
    """Load `csv_path` and run every record through the pipeline.

    Records are processed concurrently (each gets its own gate -> ... ->
    branch run); nothing about running multiple records concurrently changes
    the per-record graph shape described above.
    """
    records = load_records(csv_path)
    return await asyncio.gather(*(_run_record(record) for record in records))
