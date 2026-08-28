# Primo cleanup workflow — domain language

Ubiquitous language for the 6-node cleanup pipeline. Product tracing
terms live elsewhere; this file is only the Primo/DMR/DB2 cleanup domain.

## Enrichment

Looks up DMR and DB2 and returns a rich **finding** per source: `source`,
`details`, `data`. It does not conclude match / mismatch / gap. Empty
`data` plus a details note means the lookup found no record.

## Enrichment finding

Same type as today, minus `status`. `data` is the retrieved record (or
`{}` when none). `details` is a lookup note, not a comparison verdict.

## Diagnosis

Receives findings (no status) and the extract. Each path compares,
then emits everything it already emits — rationale, confidence, proposed
correction — plus **status**.

## Status

Owned by a diagnostic path. Three values: **match**, **mismatch**,
**gap**. Replaces `issue_found`. Diagnose infers gap from a finding with
no data.

## HITL

Unchanged: still a downstream branch (`determine_result` → `save_result`).
Not a field on enrichment or diagnosis.
