# Glossary

Shared vocabulary for AgentTrace. If a word here appears in code, an API path, or the UI, it
means what this file says it means.

## Run

One execution of an instrumented agent program — everything under a single
`Tracer(name=...)` context. In the Primo workflow a run is the processing of a whole CSV
extract.

A run is a **container**, not the thing you watch. See [Record](#record).

Runs are created implicitly by the first ingested event carrying a new `run_id`
(`IngestService.ingest_events`). Run-level completion is **not currently tracked** — every run
reads `running`. See [ADR-0004](decisions/0004-defer-run-completion.md).

## Record

**The unit of observation.** One item of work travelling through the pipeline — in the Primo
workflow, one CSV record's journey from `gate` through to `save_result`.

A record is a **projection over spans, not a stored entity**. Concretely, a record is the span
created for a source record's own `_GRAPH.ainvoke` call, identified by carrying a `record_id`
attribute. Its `id` *is* that span's id. Everything beneath it in the trace tree is that
record's work.

Why this matters: a run of the 7-record sample extract produces ~78 spans, all concurrent. A
record produces ~11, in a legible sequence. The canvas renders a record, never a run. See
[ADR-0002](decisions/0002-record-as-unit-of-observation.md).

The vocabulary matches the workflow: a record is a CSV record travelling through the pipeline,
not a generic synonym invented at the API boundary.

## Span

A recorded unit of execution inside a run: `agent_run`, `step`, `tool_call`, or `llm_call`.
Emitted by the SDK as a `span_start` / `span_end` pair, persisted as a `TraceNode` with a
`parent_id`. Spans form the execution tree — *this span caused that span* — not a pre-declared
workflow DAG.

## Node

A persisted span, as stored and served (`TraceNode` / `TraceNodeResponse`). Used
interchangeably with span when talking about the API payload rather than the act of tracing.

## Event

Custom data attached to a span: `input`, `output`, or `error`. Carries the payload — for the
Primo workflow, whole serialised pipeline state. Events are the only place a node's **error**
status is recorded, which is why the record endpoint returns them inline.

## Attribute

Key-value metadata on a span. `record_id` and `policy_id` are the load-bearing ones: their
presence on a span is what makes it a [Record](#record) root. `record_id` on the span is the
source identifier (a UUID from the CSV loader); the record's API `id` is the span's own id.

## Card

A record's span as rendered on the graph canvas. One card per node. A card has exactly one
status: `running` (no `ended_at`), `completed` (`ended_at` set), or `error` (an `error` event
present). Cards are self-coded React components, not React Flow node chrome.

Cards are not pre-rendered for work that hasn't started — unspawned work is absent, not drawn
idle.

## Invalidation ping

The only thing the streaming endpoint sends. A ping means *"this record's data changed, refetch
it"* — nothing more. It carries no span data:

```
data: {"record_id": "...", "run_id": "...", "rev": 42}
```

`record_id` here is the record's API id (the root span's id), not the source identifier
stamped on the span.

Because a ping is content-free, duplicate, out-of-order and coalesced pings are all
indistinguishable and all harmless. See
[ADR-0001](decisions/0001-invalidation-bus-over-event-stream.md).

## Rev

A monotonic per-run revision counter held in memory by the bus. Bumped once per successfully
committed ingest batch. Lets a client tell "I am already current" from "there is new work",
and gives the UI's stream indicator something honest to display.

Revs are per-process and reset when the backend restarts. They order nothing across runs and
mean nothing to the database.

## Bus

The in-process fan-out between ingest and connected browsers: a pyee `EventEmitter` plus a
dict of `run_id → rev`. Not a queue — it holds no events, only the fact that something
changed. Single-process only; running the backend with multiple workers would break it
(ingest lands on one worker, the stream on another).
