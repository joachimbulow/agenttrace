"""Node 5 -- Determine Result.

Consumes the Judge's verdict and decides the Node 6 branch based purely on
a confidence threshold. Deterministic, no business logic beyond
thresholding -- the actual "what's true" decision already happened in the
Judge step (Node 4).

OPEN QUESTION (carried forward): `CONFIDENCE_THRESHOLD` is a placeholder
(0.75), not calibrated against real data or SME input -- confirm with the
source team before relying on it for anything beyond this scaffold.
"""

from __future__ import annotations

import asyncio

from agent_trace_sdk import add_event
from langchain_core.runnables import Runnable, RunnableConfig, RunnableLambda

from agent_workflows.models.schemas import JudgeVerdict, ResultDecision
from agent_workflows.pipeline.state import PipelineState

CONFIDENCE_THRESHOLD = 0.75


def _determine_result(verdict: JudgeVerdict) -> ResultDecision:
    branch = "correct_validate" if verdict.confidence >= CONFIDENCE_THRESHOLD else "save_result"
    add_event("result", {"branch": branch, "confidence": verdict.confidence})
    return ResultDecision(verdict=verdict, branch=branch, threshold=CONFIDENCE_THRESHOLD)


determine_result_chain: Runnable[JudgeVerdict, ResultDecision] = RunnableLambda(
    _determine_result
).with_config(run_name="determine_result")


async def determine_result_node(state: PipelineState, config: RunnableConfig) -> dict:
    await asyncio.sleep(5)  # TEMP: pause so the UI can be watched during test runs
    assert state.verdict is not None
    decision = await determine_result_chain.ainvoke(state.verdict, config)
    return {"decision": decision}
