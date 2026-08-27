"""Staging area writes and the HITL / cannot-solve queue.

# MOCK -- this is a stub for the PoC. No real staging table or HITL queue
exists yet; both are in-memory lists that reset every run.

This pipeline's job stops at staging (see docs/workflow_design.md) -- actual
production migration is a separate, later step and out of scope here.
"""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class _StagingStore:
    staged: list[dict] = field(default_factory=list)
    hitl_queue: list[dict] = field(default_factory=list)


_STORE = _StagingStore()


def apply_correction(policy_id: str, correction: str | None) -> str:
    """# MOCK: apply a proposed correction to the (non-existent) source system.

    Returns a trivial confirmation string. Real implementation would write
    back to Primo/DB2 (or queue that write) once the correction is approved.
    """
    if correction is None:
        return f"No correction required for {policy_id}."
    return f"Applied correction for {policy_id}: {correction}"


def move_to_staging(policy_id: str, payload: dict) -> str:
    """# MOCK: move a validated record to the staging / ready-to-migrate area."""
    _STORE.staged.append({"policy_id": policy_id, **payload})
    return f"{policy_id} staged as ready-to-migrate."


def save_result(policy_id: str, payload: dict) -> str:
    """# MOCK: persist the result/report as-is (no correction applied)."""
    return f"Result saved for {policy_id}."


def route_to_hitl(policy_id: str, payload: dict) -> str:
    """# MOCK: route a record to the HITL / cannot-solve queue for SME review."""
    _STORE.hitl_queue.append({"policy_id": policy_id, **payload})
    return f"{policy_id} routed to HITL / cannot-solve queue."


def staged_records() -> list[dict]:
    """Inspect what has been staged so far (mock, in-memory, for the CLI summary)."""
    return list(_STORE.staged)


def hitl_records() -> list[dict]:
    """Inspect the HITL queue so far (mock, in-memory, for the CLI summary)."""
    return list(_STORE.hitl_queue)
