# 001. Diagnose owns status; enrichment does not

## Status

Accepted.

## Context

DMR and DB2 services compared the extract to a mock table and stamped
`status` on `EnrichmentFinding`. Diagnose then mapped that stamp onto
`issue_found`. Comparison ran one node too early.

A later pass over-simplified this into “drop the finding type, return
`dict | None`”. That was the wrong direction: the types stay rich;
only the conclusion moves.

## Decision

- `EnrichmentFinding` keeps `source`, `details`, and `data`. `status`
  is removed.
- Services return the retrieved record (or empty `data` + a lookup note).
  They do not compare.
- `DiagnosisProposal` keeps rationale, confidence, and proposed
  correction. It gains `status` (`match` | `mismatch` | `gap`) and
  drops `issue_found`.
- Judge, conflict, HITL, and confidence haircut stay as they are,
  reading `status == "mismatch"` where they used to read `issue_found`.

## Consequences

- Diagnose is the first place match / mismatch / gap exist.
- `workflow_design.md` Node 2 wording (enrichment produces
  match / mismatch / gap) should be updated when this lands in code.
