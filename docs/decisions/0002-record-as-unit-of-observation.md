# ADR-0002: A record, not a run, is the unit of observation

**Status:** accepted
**Date:** 2026-08-28

## Context

AgentTrace's UI has always been organised around the **run**: pick a run, see its trace. That
worked when a run was a toy two-span example.

The real workload is `agent_workflows`' Primo cleanup pipeline. `run_pipeline`
(`workflows/src/agent_workflows/pipeline/orchestrator.py`) loads a CSV and runs every record
**concurrently** through a LangGraph `StateGraph`. Each record produces roughly ten spans —
`gate`, `enrich` plus two sub-agents, `diagnose` plus three paths, `judge`,
`determine_result`, and a branch node.

For the 7-record sample extract that is one run containing ~78 spans, all in flight at once.
Rendered as a graph, that is not a visualisation of anything. It is a wall. And it obscures the
thing a developer or a client actually wants to follow: *what happened to this particular
record?*

## Decision

**The record is the unit of observation.** The canvas renders one record. The run becomes a
container you navigate through, not a thing you watch.

A **record is a projection over spans already in the database, not a new entity.**
Specifically: a record is the span created for one source record's own `_GRAPH.ainvoke` call.
Those spans are already distinguishable — `utils/tracing.py` stamps `record_id` and
`policy_id` onto exactly them, because they are the only chain runs the LangChain callback
handler sees with `parent_run_id is None`.

Therefore:

- The record's API `id` **is** the span id of that record-root span. No new identifier.
- `GET /api/v1/records?run_id=…` lists the run roots' direct children carrying a `record_id`.
- `GET /api/v1/records/{record_id}` returns that span's subtree, in the existing
  `TraceNodeResponse` shape. The path parameter is the span id (the record's API `id`).
- Record status derives from the subtree: `error` if any descendant has an `error` event, else
  `completed` if the record root has `ended_at`, else `running`.

**Vocabulary:** "record" is used everywhere — API paths, domain code, UI, this glossary. It
matches what the workflow already calls a unit of work, rather than introducing a separate
CSV-flavoured synonym at the API boundary.

The source identifier stamped on the span remains `record_id` (a UUID from the CSV loader).
The record's API `id` is the span's own id. Invalidation pings carry `record_id` meaning the
API id, because that is the identifier the stream is scoped to.

## Consequences

- **Zero schema change, zero SDK change, no migration.** The data already exists; only the way
  we slice it is new.
- **~11 cards on screen instead of ~78.** Legible, and the story has a beginning and an end.
- **Navigation gains a level:** run list → record list → canvas.
- **The stream is record-scoped in the API but run-keyed internally** — ingest only knows
  `run_id`, so the SSE route resolves record→run once at subscribe and waits on the run's flag.
  A sibling record's activity therefore wakes this stream and causes an unnecessary refetch of
  ~11 nodes. Negligible locally.
- **A record cannot exist before its first span.** A source record queued but not started is
  invisible. Consistent with the product principle that unspawned work is absent, not drawn
  idle.
- **Coupled to the LangChain callback bridge.** If `utils/tracing.py` stops stamping
  `record_id`, records silently disappear. A run with no `record_id`-bearing spans returns an
  empty record list rather than an error.

## Escape hatch, written down but not built

If the run-keyed bus's over-refetching or the ancestry-free projection becomes a problem,
denormalise a `record_id` column onto `TraceNode`, computed at insert as
`parent.record_id or (parent.id if parent is a run root else None)`. That gives exact record
topics on the write path. Do not build it before it hurts.

## Alternatives rejected

- **First-class `Record` entity** (new table, `record_start`/`record_end` SDK events) —
  cleaner conceptually, lets a record exist before its first span, but is a contract change
  across SDK, workflows and backend for no benefit we currently need.
- **Shrink the demo CSV to 1–2 records** — hides the problem instead of solving it, and throws
  away the concurrency that makes the pipeline interesting.
- **Serialise record processing** — changes production workflow behaviour for demo aesthetics.
