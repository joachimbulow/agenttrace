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

from agent_trace_sdk import trace_span

from agent_workflows.models.schemas import JudgeVerdict, ResultDecision

CONFIDENCE_THRESHOLD = 0.75


@trace_span(name="determine_result", span_type="step")
def determine_result_node(verdict: JudgeVerdict) -> ResultDecision:
    branch = "correct_validate" if verdict.confidence >= CONFIDENCE_THRESHOLD else "save_result"
    return ResultDecision(verdict=verdict, branch=branch, threshold=CONFIDENCE_THRESHOLD)
