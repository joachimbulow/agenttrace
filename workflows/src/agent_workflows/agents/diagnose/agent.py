"""Node 3 -- Diagnose / Propose: three parallel paths converge.

    1. Diagnosis driven by DMR findings
    2. Diagnosis driven by DB2 findings
    3. Diagnosis driven by rule/pattern checks

OPEN QUESTION (carried forward, do not resolve silently -- confirm with the
source team): whether "three parallel paths" really means DMR + DB2 +
rules, or something else. The rules-based third path below is an
*assumption* made to fill out the count, not a confirmed requirement. Its
"business rule" is a placeholder plate-format check standing in for the
real segmentation/locking-style checks described in
docs/workflow_design.md -- it does not implement segmentation or the
runtime locking mechanism.

Each path proposes a correction (or "no issue found") with rationale +
confidence, per the non-functional requirement that every step's output
carries rationale and confidence rather than a bare pass/fail. Match /
mismatch / gap is decided here from the enrichment data, not inherited
from it. The three paths are composed via LCEL `RunnableParallel`, which
runs them concurrently and gives each its own trace span nested under
`diagnose` (see agents/enrich/agent.py for the same pattern, and
agent_trace_sdk.langchain for how nested spans are detected).
"""

from __future__ import annotations

import asyncio
import re
from typing import Literal

from agent_trace_sdk.langchain import leaf, trace_result
from langchain_core.runnables import (
    Runnable,
    RunnableConfig,
    RunnableLambda,
    RunnableParallel,
    RunnablePassthrough,
)

from agent_workflows.models.schemas import (
    DiagnosisProposal,
    DiagnosisResult,
    EnrichmentFinding,
    EnrichmentResult,
    RawRecord,
)
from agent_workflows.pipeline.state import PipelineState

# Placeholder "business rule": a plausible Danish-style plate format.
# Stands in for a real segmentation/locking rule check (see module docstring).
_PLATE_PATTERN = re.compile(r"^[A-Z]{2}\d{5}$")
_COMPARE_FIELDS = ("plate_number", "owner_name", "vehicle_make", "vehicle_model")


def _diagnose_against_source(
    path: Literal["dmr", "db2"],
    finding: EnrichmentFinding,
    record: RawRecord,
    source_label: str,
) -> DiagnosisProposal:
    if not finding.data:
        return DiagnosisProposal(
            path=path,
            status="gap",
            proposed_correction=None,
            rationale=f"{path.upper()} path: {finding.details} -- cannot diagnose without reference data.",
            confidence=0.35,
        )

    mismatched = [
        field
        for field in _COMPARE_FIELDS
        if record.raw.get(field) != finding.data.get(field)
    ]
    if not mismatched:
        return DiagnosisProposal(
            path=path,
            status="match",
            proposed_correction=None,
            rationale=f"{path.upper()} path: record matches {source_label} on all compared fields.",
            confidence=0.95,
        )

    fields = ", ".join(mismatched)
    return DiagnosisProposal(
        path=path,
        status="mismatch",
        proposed_correction=f"Align record with {source_label} ({fields}).",
        rationale=f"{path.upper()} path: mismatch on {fields}.",
        confidence=0.85,
    )


@trace_result("path", "status", "confidence")
def _diagnose_from_dmr(enrichment: EnrichmentResult) -> DiagnosisProposal:
    return _diagnose_against_source(
        "dmr", enrichment.dmr, enrichment.gate.record, "DMR reference"
    )


@trace_result("path", "status", "confidence")
def _diagnose_from_db2(enrichment: EnrichmentResult) -> DiagnosisProposal:
    return _diagnose_against_source(
        "db2", enrichment.db2, enrichment.gate.record, "Primo DB2"
    )


@trace_result("path", "status", "confidence")
def _diagnose_from_rules(enrichment: EnrichmentResult) -> DiagnosisProposal:
    record = enrichment.gate.record
    plate = record.raw.get("plate_number", "")
    if _PLATE_PATTERN.match(plate):
        return DiagnosisProposal(
            path="rules",
            status="match",
            proposed_correction=None,
            rationale=f"Rules path: plate '{plate}' passes format check; no anomaly detected.",
            confidence=0.7,
        )
    return DiagnosisProposal(
        path="rules",
        status="mismatch",
        proposed_correction="Flag for manual plate-format review.",
        rationale=f"Rules path: plate '{plate}' fails expected format check.",
        confidence=0.6,
    )


def _merge(parts: dict) -> DiagnosisResult:
    return DiagnosisResult(
        enrichment=parts["enrichment"],
        proposals=(parts["dmr"], parts["db2"], parts["rules"]),
    )


diagnose_chain: Runnable[EnrichmentResult, DiagnosisResult] = (
    RunnableParallel(
        dmr=leaf(RunnableLambda(_diagnose_from_dmr), "diagnose_dmr_path"),
        db2=leaf(RunnableLambda(_diagnose_from_db2), "diagnose_db2_path"),
        rules=leaf(RunnableLambda(_diagnose_from_rules), "diagnose_rules_path"),
        enrichment=RunnablePassthrough(),
    )
    | RunnableLambda(_merge)
).with_config(run_name="diagnose")


@trace_result()
async def diagnose_node(state: PipelineState, config: RunnableConfig) -> dict:
    await asyncio.sleep(5)  # TEMP: pause so the UI can be watched during test runs
    assert state.enrichment is not None
    diagnosis = await diagnose_chain.ainvoke(state.enrichment, config)
    return {"diagnosis": diagnosis}
