"""DMR (external vehicle/owner reference register) access.

# MOCK -- this is a stub for the PoC. No real DMR lookup happens here.

The real DMR integration is out of scope for this scaffold (see
docs/workflow_design.md). This module defines the interface a future,
real implementation must satisfy (`lookup`), and a tiny fixed reference
table so the pipeline can run end-to-end. Comparison against the extract
happens in diagnose, not here.
"""

from __future__ import annotations

from agent_workflows.models.schemas import EnrichmentFinding, RawRecord

# MOCK reference data standing in for a real DMR query. Keyed by policy_id.
_DMR_REFERENCE: dict[str, dict[str, str]] = {
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
    "POL-1003": {
        "plate_number": "CD44444",
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
    # POL-1005 intentionally absent -> simulates a DMR data gap.
}


def lookup(record: RawRecord) -> EnrichmentFinding:
    """# MOCK: look up `record` against the DMR reference register."""
    reference = _DMR_REFERENCE.get(record.policy_id)
    if reference is None:
        return EnrichmentFinding(
            source="dmr",
            details="No DMR reference record found for this policy.",
            data={},
        )
    return EnrichmentFinding(
        source="dmr",
        details="Retrieved DMR reference record.",
        data=dict(reference),
    )
