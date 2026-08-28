# ADR-0004: Defer run-level completion

**Status:** accepted, with a known gap
**Date:** 2026-08-28

## Context

Nothing in AgentTrace ever marks a run finished. `AgentRun.complete()` and `AgentRun.fail()`
exist in the domain layer (`domain/entities/agent_run.py`) and are called by nobody. There is
no `run_end` event type in the ingest contract. `IngestService` creates every run as
`RunStatus.RUNNING` and never revisits it.

The consequence: **every run in the run list reads `running`, forever.** A run that finished
last week is indistinguishable from one executing right now.

This surfaced while designing the streaming endpoint, because a live stream normally wants a
termination signal — something that says "the run is over, stop listening, close the
connection".

## Decision

**Do not fix this now.** Streams stay open indefinitely. Run-level status remains permanently
`running` and the UI does not display it as meaningful.

Per-card status is unaffected and is what the demo actually shows:

- `running` — the node has no `ended_at`
- `completed` — `ended_at` is set
- `error` — the node has an `error` event

All three come free from data already in the trace tree. Row status derives the same way from
a row's subtree. Nothing about the live canvas depends on knowing that the *run* is over.

## Consequences

- **The stream indicator has two states, not three:** `live` and `reconnecting`. There is no
  honest `ended` state to show, so it isn't shown. A finished run's stream simply sits idle,
  emitting keepalive pings.
- **Streams never self-terminate.** A departed client is the only cleanup trigger, so the SSE
  route must check `request.is_disconnected()` each iteration or waiters accumulate.
- **The bus leaks slowly** — one `rev` entry and possibly one `asyncio.Event` per run id, never
  reclaimed. Bounded by the number of distinct runs since process start. Irrelevant for local
  use; would need eviction before this ran anywhere long-lived.
- **A killed workflow is indistinguishable from a slow one.** The UI will keep saying `live`
  after you Ctrl-C the CLI. Acceptable for a demo where the operator is the one pressing Ctrl-C.
- **The run list cannot be filtered or sorted by status** in any useful way, and
  `GET /runs?status=completed` will always return nothing.

## When to revisit

Do this properly before AgentTrace is used unattended, or as soon as anyone asks "did that
finish?" of a screen rather than of a terminal. The shape it should take:

1. The SDK emits an explicit `run_end` event carrying status and `ended_at` on tracer shutdown;
   `IngestService` routes it to `AgentRun.complete()` / `.fail()`.
2. Plus a stale sweeper — a run with no ingested events for N seconds is marked abandoned —
   because a killed process never sends step 1.

Both halves are needed. Explicit alone leaves killed runs stuck; the sweeper alone can't tell
failure from success.

## Alternatives rejected for now

- **Infer completion from the root `agent_run` span ending** — no SDK contract change, but
  fragile: the root span's `span_end` is emitted before child export tasks have necessarily
  flushed, so the run would go green while spans were still arriving.
