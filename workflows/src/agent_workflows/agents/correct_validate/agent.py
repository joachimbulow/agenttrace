"""Node 6, Path A -- Correct / Validate (high confidence).

(1) apply the proposed correction (mocked), (2) move the record to
Staging / Ready to Migrate (mocked). Both external effects live in
services/staging_service.py, marked `# MOCK` there.
"""

from __future__ import annotations

from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from agent_workflows.models.schemas import PipelineOutcome, ResultDecision
from agent_workflows.pipeline.state import PipelineState
from agent_workflows.services import staging_service


def _correct_validate(decision: ResultDecision) -> PipelineOutcome:
    verdict = decision.verdict
    record = verdict.diagnosis.enrichment.gate.record
    correction = (
        verdict.selected_proposal.proposed_correction if verdict.selected_proposal else None
    )

    apply_summary = staging_service.apply_correction(record.policy_id, correction)
    stage_summary = staging_service.move_to_staging(
        record.policy_id,
        {
            "task_type": record.task_type,
            "rationale": verdict.rationale,
            "confidence": verdict.confidence,
        },
    )

    return PipelineOutcome(
        policy_id=record.policy_id,
        task_type=record.task_type,
        known=True,
        branch="correct_validate",
        confidence=verdict.confidence,
        summary=f"{apply_summary} {stage_summary}",
    )


correct_validate_chain: Runnable[ResultDecision, PipelineOutcome] = RunnableLambda(
    _correct_validate
).with_config(run_name="correct_validate")


async def correct_validate_node(state: PipelineState, config: RunnableConfig) -> dict:
    assert state.decision is not None
    outcome = await correct_validate_chain.ainvoke(state.decision, config)
    return {"outcome": outcome}
