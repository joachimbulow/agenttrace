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
carries rationale and confidence rather than a bare pass/fail. The three
paths are composed via LCEL `RunnableParallel`, which runs them
concurrently and gives each its own trace span nested under `diagnose`
(see agents/enrich/agent.py for the same pattern, and utils/tracing.py for
how nested spans are detected).
"""

from __future__ import annotations

import re

from langchain_core.runnables import Runnable, RunnableLambda, RunnableParallel, RunnablePassthrough

from agent_workflows.models.schemas import DiagnosisProposal, DiagnosisResult, EnrichmentResult
from agent_workflows.utils.tracing import leaf

# Placeholder "business rule": a plausible Danish-style plate format.
# Stands in for a real segmentation/locking rule check (see module docstring).
_PLATE_PATTERN = re.compile(r"^[A-Z]{2}\d{5}$")


def _diagnose_from_dmr(enrichment: EnrichmentResult) -> DiagnosisProposal:
    finding = enrichment.dmr
    if finding.status == "match":
        return DiagnosisProposal(
            path="dmr",
            issue_found=False,
            proposed_correction=None,
            rationale=f"DMR path: {finding.details}",
            confidence=0.95,
        )
    if finding.status == "mismatch":
        return DiagnosisProposal(
            path="dmr",
            issue_found=True,
            proposed_correction=f"Align record with DMR reference ({finding.details})",
            rationale=f"DMR path: {finding.details}",
            confidence=0.85,
        )
    return DiagnosisProposal(
        path="dmr",
        issue_found=False,
        proposed_correction=None,
        rationale=f"DMR path: {finding.details} -- cannot diagnose without reference data.",
        confidence=0.35,
    )


def _diagnose_from_db2(enrichment: EnrichmentResult) -> DiagnosisProposal:
    finding = enrichment.db2
    if finding.status == "match":
        return DiagnosisProposal(
            path="db2",
            issue_found=False,
            proposed_correction=None,
            rationale=f"DB2 path: {finding.details}",
            confidence=0.95,
        )
    if finding.status == "mismatch":
        return DiagnosisProposal(
            path="db2",
            issue_found=True,
            proposed_correction=f"Align record with Primo DB2 ({finding.details})",
            rationale=f"DB2 path: {finding.details}",
            confidence=0.85,
        )
    return DiagnosisProposal(
        path="db2",
        issue_found=False,
        proposed_correction=None,
        rationale=f"DB2 path: {finding.details} -- cannot diagnose without reference data.",
        confidence=0.35,
    )


def _diagnose_from_rules(enrichment: EnrichmentResult) -> DiagnosisProposal:
    record = enrichment.gate.record
    plate = record.raw.get("plate_number", "")
    if _PLATE_PATTERN.match(plate):
        return DiagnosisProposal(
            path="rules",
            issue_found=False,
            proposed_correction=None,
            rationale=f"Rules path: plate '{plate}' passes format check; no anomaly detected.",
            confidence=0.7,
        )
    return DiagnosisProposal(
        path="rules",
        issue_found=True,
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
