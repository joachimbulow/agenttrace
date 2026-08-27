"""Primo DB2 read access (vehicle/policy record lookup).

# MOCK -- this is a stub for the PoC. No real DB2 query happens here.

Real access is read-only, request-based (ServiceNow) and constrained to
non-production hours (see docs/workflow_design.md) -- none of that applies
here. This module defines the interface a future, real implementation must
satisfy (`lookup`), backed by a tiny fixed table so the pipeline produces
varied, demoable findings.

Deliberately independent from dmr_service's reference table: for POL-1003
the two "sources" disagree with each other, to exercise the judge's
conflict-detection path.
"""

from __future__ import annotations

from agent_workflows.models.schemas import EnrichmentFinding, RawRecord

# MOCK Primo DB2 vehicle table. Keyed by policy_id.
_DB2_VEHICLE_TABLE: dict[str, dict[str, str]] = {
    "POL-1001": {
        "plate_number": "AB12345",
        "owner_name": "Anna Larsen",
        "vehicle_make": "Volvo",
        "vehicle_model": "V60",
    },
    "POL-1002": {
        "plate_number": "AB99999",
        "owner_name": "Bo Madsen",
        "vehicle_make": "Volvo",
        "vehicle_model": "XC60",
    },
    # Deliberately disagrees with the DMR reference for the same policy,
    # to simulate two sources disagreeing with each other.
    "POL-1003": {
        "plate_number": "CD00000",
        "owner_name": "Cecilie Holm",
        "vehicle_make": "Toyota",
        "vehicle_model": "Corolla",
    },
    "POL-1006": {
        "plate_number": "EF77777",
        "owner_name": "Erik Nissen",
        "vehicle_make": "Skoda",
        "vehicle_model": "Octavia",
    },
    "POL-1007": {
        "plate_number": "GH11111",
        "owner_name": "Gitte Poulsen",
        "vehicle_make": "Kia",
        "vehicle_model": "Ceed",
    },
    # POL-1005 intentionally absent -> simulates a DB2 data gap.
}

_COMPARE_FIELDS = ("plate_number", "owner_name", "vehicle_make", "vehicle_model")


def lookup(record: RawRecord) -> EnrichmentFinding:
    """# MOCK: look up `record` against Primo's DB2 vehicle table."""
    reference = _DB2_VEHICLE_TABLE.get(record.policy_id)
    if reference is None:
        return EnrichmentFinding(
            source="db2",
            status="gap",
            details="No DB2 vehicle record found for this policy (data gap).",
            data={},
        )

    mismatched = {
        field: (record.raw.get(field), reference[field])
        for field in _COMPARE_FIELDS
        if record.raw.get(field) != reference[field]
    }

    if not mismatched:
        return EnrichmentFinding(
            source="db2",
            status="match",
            details="Record matches Primo DB2 vehicle table on all compared fields.",
            data=dict(reference),
        )

    fields = ", ".join(mismatched)
    return EnrichmentFinding(
        source="db2",
        status="mismatch",
        details=f"DB2 mismatch on: {fields}.",
        data={"reference": dict(reference), "mismatched_fields": mismatched},
    )
