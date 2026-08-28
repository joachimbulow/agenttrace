"""Node 1 -- Gate: "do we know this task?"

Filter before any enrichment. Only recognized task types proceed. PoC scope
is just `12_11`, but kept as a configurable set (see KNOWN_TASK_TYPES) rather
than a hardcoded single literal, per docs/workflow_design.md section 1.

Implemented as a plain LCEL `Runnable` (no parallel composition needed).
`gate_node` is what the orchestrator wires; `reject_node` is the unknown-task
early exit from this same stage. See utils/tracing.py for how node spans
are produced.
"""

from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from agent_workflows.models.schemas import GateResult, PipelineOutcome, RawRecord
from agent_workflows.pipeline.state import PipelineState

# Configuration, not a hardcoded literal: which task types this PoC knows
# how to handle. Extend as more task types are onboarded.
KNOWN_TASK_TYPES: frozenset[str] = frozenset({"12_11"})


def _gate(record: RawRecord) -> GateResult:
    if record.task_type in KNOWN_TASK_TYPES:
        return GateResult(
            record=record, known=True, reason=f"task_type '{record.task_type}' recognized."
        )
    return GateResult(
        record=record,
        known=False,
        reason=f"task_type '{record.task_type}' not in known set {sorted(KNOWN_TASK_TYPES)}; rejected.",
    )


gate_chain: Runnable[RawRecord, GateResult] = RunnableLambda(_gate).with_config(run_name="gate")


async def gate_node(state: PipelineState, config: RunnableConfig) -> dict:
    gate = await gate_chain.ainvoke(state.record, config)
    return {"gate": gate}


def reject_node(state: PipelineState) -> dict:
    assert state.gate is not None
    gate = state.gate
    return {
        "outcome": PipelineOutcome(
            policy_id=gate.record.policy_id,
            task_type=gate.record.task_type,
            known=False,
            branch=None,
            confidence=None,
            summary=gate.reason,
            record_id=gate.record.record_id,
        )
    }
