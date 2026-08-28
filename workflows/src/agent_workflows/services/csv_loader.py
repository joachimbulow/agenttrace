"""Real (not mocked) local CSV read.

The one non-mocked "service" in this scaffold: everything else under
services/ talks to a system that doesn't exist yet for this PoC (DMR, DB2,
staging), but reading a local CSV file is real.

NOTE (open question, see README): the real Primo extract schema is not
finalized. This loader is deliberately schema-tolerant -- it only requires
`policy_id` and `task_type` to exist as columns, and passes every other
column through untouched in `RawRecord.raw`. Adjust the required-columns set
once the real schema is known.
"""

from __future__ import annotations

import csv
from pathlib import Path
from uuid import uuid4

from agent_workflows.models.schemas import RawRecord

REQUIRED_COLUMNS = ("policy_id", "task_type")


def load_records(csv_path: str | Path) -> list[RawRecord]:
    """Load records from `csv_path` into `RawRecord`s.

    Raises `ValueError` if a required column is missing, but otherwise makes
    no assumptions about the rest of the schema.
    """
    path = Path(csv_path)
    records: list[RawRecord] = []

    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        missing = [c for c in REQUIRED_COLUMNS if c not in fieldnames]
        if missing:
            raise ValueError(f"CSV missing required columns: {missing}")

        for record in reader:
            raw = dict(record)
            policy_id = raw.pop("policy_id")
            task_type = raw.pop("task_type")
            records.append(
                RawRecord(
                    policy_id=policy_id,
                    task_type=task_type,
                    record_id=str(uuid4()),
                    raw=raw,
                )
            )

    return records
