"""Node 4 -- LLM as a Judge.

# MOCK -- no real LLM call happens here. This is a deterministic stub
standing in for a future real LLM-as-judge call, hence the `judge` graph
node is tagged `span_type="llm_call"` (see pipeline/orchestrator.py) even
though nothing here calls out to a model yet.

Reviews the (possibly conflicting) proposals from the three diagnostic
paths and adjudicates a single recommended outcome + confidence, using a
fixed/templated rationale string.

Implementation choice (flag this -- it narrows open question #1 without
fully resolving it): "conflict" is defined here as the DMR-driven and
DB2-driven paths disagreeing on whether the status is a mismatch. The
rules-based path (itself an assumption, see agents/diagnose/agent.py)
still counts toward which proposal gets *selected* -- it is treated as a
supplementary/tie-breaking signal, not as a source of "conflict" -- since
it inspects a different concern (format anomalies) than the two
source-driven paths. Revisit once the source team confirms what the third
path is actually meant to check.
"""

from __future__ import annotations

import asyncio

from agent_trace_sdk.langchain import trace_result
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from agent_workflows.models.schemas import DiagnosisResult, JudgeVerdict
from agent_workflows.pipeline.state import PipelineState

# Deliberate confidence haircut applied when the two source-driven paths
# (DMR, DB2) disagree with each other -- pushes conflicted cases toward the
# HITL branch in Node 5. Placeholder magnitude, not calibrated.
_CONFLICT_PENALTY = 0.6


def _judge(diagnosis: DiagnosisResult) -> JudgeVerdict:
    proposals = diagnosis.proposals
    by_path = {p.path: p for p in proposals}
    dmr_proposal = by_path.get("dmr")
    db2_proposal = by_path.get("db2")

    conflict = (
        dmr_proposal is not None
        and db2_proposal is not None
        and (dmr_proposal.status == "mismatch") != (db2_proposal.status == "mismatch")
    )

    selected = max(proposals, key=lambda p: p.confidence, default=None)
    if selected is None:
        return JudgeVerdict(
            diagnosis=diagnosis,
            selected_proposal=None,
            conflict=True,
            confidence=0.0,
            rationale="# MOCK judge: no proposals to adjudicate.",
        )

    confidence = selected.confidence * _CONFLICT_PENALTY if conflict else selected.confidence

    if conflict:
        rationale = (
            f"# MOCK judge: DMR and DB2 paths disagree (conflict=True). "
            f"Provisionally selected highest-confidence proposal from '{selected.path}' "
            f"({selected.confidence:.2f}) but discounted confidence to {confidence:.2f} "
            f"pending SME review."
        )
    else:
        rationale = (
            f"# MOCK judge: paths agree (conflict=False). Adopting proposal from "
            f"'{selected.path}' with confidence {confidence:.2f}."
        )

    return JudgeVerdict(
        diagnosis=diagnosis,
        selected_proposal=selected,
        conflict=conflict,
        confidence=confidence,
        rationale=rationale,
    )


judge_chain: Runnable[DiagnosisResult, JudgeVerdict] = RunnableLambda(_judge).with_config(
    run_name="judge"
)


@trace_result("conflict", "confidence")
async def judge_node(state: PipelineState, config: RunnableConfig) -> dict:
    await asyncio.sleep(5)  # TEMP: pause so the UI can be watched during test runs
    assert state.diagnosis is not None
    verdict = await judge_chain.ainvoke(state.diagnosis, config)
    return {"verdict": verdict}
