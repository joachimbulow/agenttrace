"""Graph state threaded through the pipeline for one record.

Lives in its own module so agent nodes can type against `PipelineState`
without importing the orchestrator (which would be a circular import:
orchestrator wires the nodes, nodes must not import the wiring).

A dataclass (not TypedDict) so it satisfies LangGraph's `StateT` bound
(`DataclassLike`) under Pyrefly, which does not treat TypedDict as matching
`TypedDictLikeV1` / `TypedDictLikeV2`.
"""

from __future__ import annotations

from dataclasses import dataclass

from agent_workflows.models.schemas import (
    DiagnosisResult,
    EnrichmentResult,
    GateResult,
    JudgeVerdict,
    PipelineOutcome,
    RawRecord,
    ResultDecision,
)


@dataclass
class PipelineState:
    """State threaded through the graph for one record. Each field is
    written by exactly one node, so no custom reducers are needed.

    `record` is the graph input; remaining fields are filled as nodes run
    and default to None until then.
    """

    record: RawRecord
    gate: GateResult | None = None
    enrichment: EnrichmentResult | None = None
    diagnosis: DiagnosisResult | None = None
    verdict: JudgeVerdict | None = None
    decision: ResultDecision | None = None
    outcome: PipelineOutcome | None = None
