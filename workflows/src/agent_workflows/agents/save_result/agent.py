"""Node 6, Path B -- Save Result (low confidence / unresolved).

(1) persist the result/report as-is (mocked), (2) route to the HITL /
cannot-solve queue (mocked). Both external effects live in
services/staging_service.py, marked `# MOCK` there. HITL is a hard gate
here -- this path is never skipped for low-confidence/conflicted cases.
"""

from __future__ import annotations

import asyncio

from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from agent_workflows.models.schemas import PipelineOutcome, ResultDecision
from agent_workflows.pipeline.state import PipelineState
from agent_workflows.services import staging_service


def _save_result(decision: ResultDecision) -> PipelineOutcome:
    verdict = decision.verdict
    record = verdict.diagnosis.enrichment.gate.record

    save_summary = staging_service.save_result(
        record.policy_id,
        {
            "task_type": record.task_type,
            "rationale": verdict.rationale,
            "confidence": verdict.confidence,
        },
    )
    hitl_summary = staging_service.route_to_hitl(
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
        branch="save_result",
        confidence=verdict.confidence,
        summary=f"{save_summary} {hitl_summary}",
        record_id=record.record_id,
    )


save_result_chain: Runnable[ResultDecision, PipelineOutcome] = RunnableLambda(
    _save_result
).with_config(run_name="save_result")


async def save_result_node(state: PipelineState, config: RunnableConfig) -> dict:
    await asyncio.sleep(5)  # TEMP: pause so the UI can be watched during test runs
    assert state.decision is not None
    outcome = await save_result_chain.ainvoke(state.decision, config)
    return {"outcome": outcome}
