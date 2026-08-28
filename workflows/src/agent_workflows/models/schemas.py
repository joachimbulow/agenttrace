"""Shared data contracts between all pipeline nodes.

Plain dataclasses, no framework magic -- every node reads/writes these, never
a raw dict, so the shape of the data crossing node boundaries is explicit.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal
from uuid import uuid4

Branch = Literal["correct_validate", "save_result"]


@dataclass(frozen=True)
class RawRecord:
    """One row from the CSV extract, loosely typed on purpose.

    NOTE: the real Primo extract schema is not finalized yet (see README ->
    "Known open questions"). Only `policy_id` and `task_type` are assumed to
    exist; everything else lives in `raw` so the loader survives schema
    changes without code edits.
    """

    policy_id: str
    task_type: str
    record_id: str = field(default_factory=lambda: str(uuid4()))
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class GateResult:
    """Output of Node 1 -- Gate."""

    record: RawRecord
    known: bool
    reason: str


@dataclass(frozen=True)
class EnrichmentFinding:
    """One sub-agent's lookup result, produced independently in Node 2.

    `data` is the retrieved record, or `{}` when the lookup found no row.
    `details` is a lookup note. Comparison (match / mismatch / gap) lives
    on `DiagnosisProposal.status`, not here.
    """

    source: Literal["dmr", "db2"]
    details: str
    data: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class EnrichmentResult:
    """Merged output of Node 2 (the two parallel sub-agents)."""

    gate: GateResult
    dmr: EnrichmentFinding
    db2: EnrichmentFinding


@dataclass(frozen=True)
class DiagnosisProposal:
    """One diagnostic path's proposal, produced independently in Node 3."""

    path: Literal["dmr", "db2", "rules"]
    status: Literal["match", "mismatch", "gap"]
    proposed_correction: str | None
    rationale: str
    confidence: float


@dataclass(frozen=True)
class DiagnosisResult:
    """Merged output of Node 3 (the three parallel diagnostic paths)."""

    enrichment: EnrichmentResult
    proposals: tuple[DiagnosisProposal, ...]


@dataclass(frozen=True)
class JudgeVerdict:
    """Output of Node 4 -- LLM-as-a-judge (mocked, see judge/agent.py)."""

    diagnosis: DiagnosisResult
    selected_proposal: DiagnosisProposal | None
    conflict: bool
    confidence: float
    rationale: str


@dataclass(frozen=True)
class ResultDecision:
    """Output of Node 5 -- Determine Result. Governs the Node 6 branch."""

    verdict: JudgeVerdict
    branch: Branch
    threshold: float


@dataclass(frozen=True)
class PipelineOutcome:
    """Final, per-record outcome returned by the orchestrator for reporting."""

    policy_id: str
    task_type: str
    known: bool
    branch: Branch | None
    confidence: float | None
    summary: str
    record_id: str
    run_id: str | None = None
