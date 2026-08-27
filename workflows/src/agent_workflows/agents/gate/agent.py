"""Node 1 -- Gate: "do we know this task?"

Filter before any enrichment. Only recognized task types proceed. PoC scope
is just `12_11`, but kept as a configurable set (see KNOWN_TASK_TYPES) rather
than a hardcoded single literal, per docs/workflow_design.md section 1.

Implemented as a plain LCEL `Runnable` (no parallel composition needed).
The graph node wrapping this in pipeline/orchestrator.py is what produces
its trace span -- see utils/tracing.py.
"""

from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableLambda

from agent_workflows.models.schemas import GateResult, RawRecord

# Configuration, not a hardcoded literal: which task types this PoC knows
# how to handle. Extend as more task types are onboarded.
KNOWN_TASK_TYPES: frozenset[str] = frozenset({"12_11"})


def _gate(record: RawRecord) -> GateResult:
    if record.task_type in KNOWN_TASK_TYPES:
        return GateResult(record=record, known=True, reason=f"task_type '{record.task_type}' recognized.")
    return GateResult(
        record=record,
        known=False,
        reason=f"task_type '{record.task_type}' not in known set {sorted(KNOWN_TASK_TYPES)}; rejected.",
    )


gate_chain: Runnable[RawRecord, GateResult] = RunnableLambda(_gate).with_config(run_name="gate")
