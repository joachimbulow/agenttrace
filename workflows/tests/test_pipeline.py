from __future__ import annotations

import asyncio
from pathlib import Path

from agent_workflows.agents.gate.agent import KNOWN_TASK_TYPES, gate_chain
from agent_workflows.models.schemas import RawRecord
from agent_workflows.pipeline.orchestrator import run_pipeline
from agent_workflows.services.csv_loader import load_records

DATA_DIR = Path(__file__).resolve().parents[1] / "data"
SAMPLE_CSV = DATA_DIR / "sample_extract.csv"


def test_gate_accepts_known_task_type() -> None:
    record = RawRecord(policy_id="POL-X", task_type="12_11", raw={})
    result = gate_chain.invoke(record)
    assert result.known is True


def test_gate_rejects_unknown_task_type() -> None:
    record = RawRecord(policy_id="POL-X", task_type="99_99", raw={})
    result = gate_chain.invoke(record)
    assert result.known is False
    assert "99_99" in result.reason


def test_load_records_is_schema_tolerant() -> None:
    records = load_records(SAMPLE_CSV)
    assert len(records) == 7
    assert all(isinstance(r.raw, dict) for r in records)
    # Extra columns beyond policy_id/task_type pass through untouched.
    assert "plate_number" in records[0].raw
    ids = [r.record_id for r in records]
    assert all(ids)
    assert len(set(ids)) == len(ids)


def test_pipeline_runs_end_to_end_over_sample_fixture() -> None:
    outcomes = asyncio.run(run_pipeline(str(SAMPLE_CSV)))

    assert len(outcomes) == 7

    unknown = [o for o in outcomes if not o.known]
    known = [o for o in outcomes if o.known]

    # Exactly the unrecognized task_type row should be rejected at the gate.
    assert {o.policy_id for o in unknown} == {"POL-1004"}
    assert all(o.branch is None for o in unknown)

    # Every known record must produce one of the two Node 6 branches, never
    # a bare pass/fail, and must carry a confidence score.
    for outcome in known:
        assert outcome.branch in ("correct_validate", "save_result")
        assert outcome.confidence is not None
        assert outcome.summary

    # The sample fixture is tuned so a full run produces a mix of both
    # branches, not everything collapsing onto one (see README).
    branches = {o.branch for o in known}
    assert branches == {"correct_validate", "save_result"}

    record_ids = [o.record_id for o in outcomes]
    assert all(record_ids)
    assert len(set(record_ids)) == len(record_ids)


def test_known_task_types_is_configurable_not_a_single_literal() -> None:
    assert isinstance(KNOWN_TASK_TYPES, frozenset)
    assert "12_11" in KNOWN_TASK_TYPES
