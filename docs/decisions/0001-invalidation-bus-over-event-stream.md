# ADR-0001: Invalidation bus, not an event stream

**Status:** accepted
**Date:** 2026-08-28
**Supersedes:** the event-contract and SSE-payload sections of `plans/live-run-graph.md`

## Context

The UI needed to update while an agent run is in flight. The backend already persists each
span as it arrives; the only missing piece was fan-out to the browser.

The obvious design — and the one the earlier plan specified — is to push the trace events
themselves over SSE and have the frontend maintain a reducer that rebuilds the tree from them.

That design has a hidden cost. `Tracer._schedule` (`sdk/src/agent_trace_sdk/tracer.py`) fires
each flush as an independent asyncio task, so flushes race and arrive over separate concurrent
HTTP POSTs. A child's `span_start` genuinely can reach the backend before its parent's. A
frontend reducer consuming raw events therefore needs:

- orphan buffering (hold a child until its parent shows up)
- per-run sequence numbers to detect gaps
- a server-side replay buffer and `Last-Event-ID` handling for reconnects
- a bounded per-subscriber queue and a drop policy for backpressure
- and a resync path for when that drop policy fires

All of that is machinery for keeping two copies of the truth in agreement.

## Decision

**SSE carries an invalidation ping, not data.** The payload is
`{record_id, run_id, rev}`. On receiving one, the client refetches `GET /api/v1/records/{record_id}`.
The server's stored tree is the only representation of the truth; the client never
reconstructs it.

The bus is not a queue. It is a per-run revision counter plus a swappable `asyncio.Event`:

```python
def publish(self, run_id):
    self._revs[run_id] = self._revs.get(run_id, 0) + 1
    ev = self._events.pop(run_id, None)
    if ev: ev.set()

async def wait(self, run_id, since_rev):
    while True:
        rev = self._revs.get(run_id, 0)
        if rev > since_rev:
            return rev
        await self._events.setdefault(run_id, asyncio.Event()).wait()
```

## Consequences

**Deleted outright:** sequence numbers, replay buffer, `Last-Event-ID`, orphan buffering,
per-subscriber queues, bounded-queue drop policy, resync protocol.

**Coalescing is inherent.** A waiter re-reads `rev` rather than draining a queue, so twenty
spans landing while a client is mid-fetch wake it exactly once. Backpressure cannot occur:
a slow client simply observes a larger jump in `rev`.

**Out-of-order and duplicate delivery are structurally irrelevant.** Every ping means the same
thing. A missed ping delays an update; it can never corrupt one.

**Publish must happen after commit.** `get_session` commits in FastAPI's dependency teardown,
*after* the route handler returns. Publishing inside `IngestService` would let a client refetch
pre-commit, see nothing, and then never be told again. The ingest route therefore publishes via
`BackgroundTasks`, which runs after yield-dependencies are finalised. This is the subtlest
correctness point in the design and is covered by a test.

**The refetch is a whole subtree.** ~11 nodes per record including event payloads. Cheap here;
would not be at production trace volumes.

**Latency floor** is one round trip rather than a push. Locally, imperceptible.

**Genuinely harder later:** token-level streaming (an LLM response arriving word by word) does
not fit an invalidation model. If that becomes a requirement, it wants its own narrow channel
rather than a rewrite of this one.

## Alternatives rejected

- **Fat events over SSE** — all the machinery above, for a latency win that doesn't matter on
  localhost.
- **Polling `/tree` every 300ms** (the earlier plan's fallback) — same refetch cost, but
  constant regardless of activity, and visibly laggy at the moment a card should appear.
