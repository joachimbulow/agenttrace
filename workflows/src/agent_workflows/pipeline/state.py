"""Graph state threaded through the pipeline for one record.

Lives in its own module so agent nodes can type against `PipelineState`
without importing the orchestrator (which would be a circular import:
orchestrator wires the nodes, nodes must not import the wiring).
"""

from __future__ import annotations

from typing import TypedDict

from agent_workflows.models.schemas import (
    DiagnosisResult,
    EnrichmentResult,
    GateResult,
    JudgeVerdict,
    PipelineOutcome,
    RawRecord,
    ResultDecision,
)


class PipelineState(TypedDict, total=False):
    """State threaded through the graph for one record. Each key is
    written by exactly one node, so no custom reducers are needed."""

    record: RawRecord
    gate: GateResult
    enrichment: EnrichmentResult
    diagnosis: DiagnosisResult
    verdict: JudgeVerdict
    decision: ResultDecision
    outcome: PipelineOutcome
