# Live run graph (handoff)

> **PARTIALLY SUPERSEDED.** This document's motivation and its inventory of what exists still
> hold, but three of its design choices were reversed after a design review. See:
>
> - `docs/decisions/0001-invalidation-bus-over-event-stream.md` — SSE carries an invalidation
>   ping, **not** the event payloads described in "Event contract" below. The frontend reducer
>   sketched there does not exist.
> - `docs/decisions/0002-row-as-unit-of-observation.md` — the canvas renders **one row**, not a
>   whole run. `GET /runs/{id}/events` was replaced by `GET /rows/{row_id}/events`.
> - `docs/decisions/0004-defer-run-completion.md` — there is no `run_status` event type and
>   streams do not close.
>
> "Slice 1 (SDK: timely export)" is already done — the SDK flushes on every span boundary.

**Status:** not started — design only  
**Goal:** show a run as a **node graph that updates while work is in flight**, not a static indented list fetched once.  
**PoC constraint:** stay local-first. Do not add Redis unless we outgrow a single FastAPI process.

## Why this is possible

The backend already stores a tree, not a flat log:

- Ingest: `POST /api/v1/ingest/events` (`span_start` / `span_end` / `span_event`)
- Read: `GET /api/v1/runs/{id}/tree` → `TraceNode` with `parent_id` (as children), `ended_at: null` while running
- SDK already emits those events; they are just **batched** and the UI is **one-shot**

The indented TraceTree in `frontend/src/components/TraceTree` is a presentation choice. The same payload drives the growing-card canvas in [frontend-redesign.md](./frontend-redesign.md).

This graph is the **execution tree** (this span caused that span). It is **not** LangGraph’s compiled DAG, and it is **not** a pre-drawn definition that lights up. For a client demo of “what is running now,” nodes spawn as work starts. Visual/UX contract (clean canvas, self-coded cards, nested packages, fluid size) lives in the redesign brief; this document is the data pipe.

## What exists today (gaps)

| Layer | Today | Gap |
| --- | --- | --- |
| SDK | `BatchSpanProcessor` (flush at 100 events or 5s) | Live UI can lag several seconds |
| Backend | Persist on ingest, REST read | No fan-out to browsers |
| Frontend | `useRunTree` fetches once | No poll / SSE / WS; tree is a nested list |

Also: SDK sync `Tracer` + missing `logger` in processor was a crash path; logger is fixed. Sync context still warns; live demo is happier if the wait/workflow path is async so flush is not `asyncio.run` from sync `__exit__`.

## Recommended design (PoC)

**Do not start with Redis.** One backend + one UI: in-process pub/sub + **SSE**.

```
workflow (spans)
    → SDK (flush on span_start/end, not only batch timeout)
    → POST /ingest/events
    → IngestService persists + publish(run_id, event)
    → GET /runs/{id}/events  (text/event-stream)
    → frontend patches graph nodes
```

Redis pub/sub is the same contract with an extra hop. Revisit only if ingest and API are separate processes.

**Polling fallback:** `GET /runs/{id}/tree` every ~300ms while `status === running`. Ugly but a valid 1-hour slice if SSE slips. Prefer SSE for the demo.

## Event contract

Reuse ingest event shapes. SSE payload example:

```json
{
  "run_id": "...",
  "type": "span_start | span_end | span_event | run_status",
  "span_id": "...",
  "parent_id": "...",
  "name": "wait",
  "span_type": "step",
  "ended_at": null
}
```

Frontend reducer:

- `span_start` → spawn a card (`running`). If the parent is a package (e.g. Enrich), insert as a nested card inside it; otherwise add a top-level node and an orthogonal edge from `parent_id`. Unspawned work stays absent.
- `span_end` → mark completed, set duration; reflow only if measured size changed
- `span_event` → attach to card details (do not relayout unless content size changed)
- `run_status` → completed/failed, close SSE

Initial snapshot: first SSE event or a normal `GET .../tree` then subscribe so late joiners are not empty.

## Implementation slices

### 1. SDK: timely export

**Where:** `sdk/src/agent_trace_sdk/processor.py`, tracer start/end.

- Flush on `span_start` and `span_end` (or `max_size=1` / `timeout_ms` ~100–200 for local).
- Keep batching as a config, default it aggressive in the workflows package.
- Prefer async `trace_agent_run` / `asyncio.sleep` in dummy wait so export uses the running loop.

### 2. Backend: bus + SSE

**Where:** `application/services` ingest; new `presentation/routers` stream.

- Tiny `RunEventBus` (asyncio queues keyed by `run_id`, last-N buffer optional).
- After successful persist in `IngestService.ingest_events`, `await bus.publish(...)`.
- `GET /api/v1/runs/{run_id}/events` → `StreamingResponse` SSE, `Cache-Control: no-cache`.
- CORS already on; EventSource is GET (no custom headers) — fine with current CORS if origin is allowed.

### 3. Frontend: graph canvas

**Where:** new `frontend/src/components/RunGraph/` next to TraceTree; keep the list as a fallback tab.

- React Flow (xyflow) as a **dumb canvas** only — custom node types, custom orthogonal edges, hide default background / controls / minimap. Cards are self-coded (shadcn); see [frontend-redesign.md](./frontend-redesign.md).
- Spawn, don’t pre-layout: `span_start` adds a node (or a nested card inside its package). Do not dagre the full DAG up front. Unspawned work is absent.
- Nested agents (e.g. Enrich → DMR | DB2) render as cards *inside* the parent node, not as extra top-level nodes.
- Nodes measure their content and update size; reflow on size change so fluid expand doesn’t overlap. Do not relayout the whole graph on a text-only `span_event`.
- `EventSource` on `/api/v1/runs/{id}/events`; reconnect on error.

### 4. Dummy workflow as the demo script

**Where:** `workflows/` dummy wait — optionally two sequential wait nodes so the graph grows.

- Run with backend + frontend up.
- Open run → graph: root card spawns, then the next card appears (nested or successor), then completed.

## Out of scope (unless a client asks)

- Redis / NATS / Kafka
- LangGraph compiled-graph overlay (static edges vs run tree)
- Auth on SSE
- Multi-tab presence, run comparison, waterfall
- Token/cost on nodes

## Suggested order if time is short

1. Polling + React Flow on existing tree API (visible graph, “live enough”).
2. SDK flush-on-span (feels live).
3. SSE (drops polling).

## Touch list (for the next agent)

- `sdk/src/agent_trace_sdk/processor.py` — flush policy
- `sdk/src/agent_trace_sdk/tracer.py` — async path if still using sync CLI
- `backend/.../application/services/` ingest + new event bus
- `backend/.../presentation/routers/runs.py` — SSE route
- `frontend/src/hooks/` — `useRunEvents`
- `frontend/src/components/RunGraph/`
- `workflows/src/agent_workflows/` — extra wait node for a 2-node tree
- `docker-compose.yml` — unchanged unless Redis is explicitly chosen later

## Done when

- Starting `uv run wait-flow --seconds 3` with UI open shows the root card spawn, then a running `wait` child appear, then both completed, without refresh.
- TraceTree list still works.
- Backend down: workflow still finishes (export failure must not kill the run).
