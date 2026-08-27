"""Node 6, Path B -- Save Result (low confidence / unresolved).

(1) persist the result/report as-is (mocked), (2) route to the HITL /
cannot-solve queue (mocked). Both external effects live in
services/staging_service.py, marked `# MOCK` there. HITL is a hard gate
here -- this path is never skipped for low-confidence/conflicted cases.
"""

from __future__ import annotations

from agent_trace_sdk import trace_span

from agent_workflows.models.schemas import PipelineOutcome, ResultDecision
from agent_workflows.services import staging_service


@trace_span(name="save_result", span_type="step")
def save_result_node(decision: ResultDecision) -> PipelineOutcome:
    verdict = decision.verdict
    record = verdict.diagnosis.enrichment.gate.record

    save_summary = staging_service.save_result(
        record.policy_id,
        {"task_type": record.task_type, "rationale": verdict.rationale, "confidence": verdict.confidence},
    )
    hitl_summary = staging_service.route_to_hitl(
        record.policy_id,
        {"task_type": record.task_type, "rationale": verdict.rationale, "confidence": verdict.confidence},
    )

    return PipelineOutcome(
        policy_id=record.policy_id,
        task_type=record.task_type,
        known=True,
        branch="save_result",
        confidence=verdict.confidence,
        summary=f"{save_summary} {hitl_summary}",
    )
