# SDK assessment: fix it, or switch?

**Verdict: fix the SDK.** It is not too far gone. Switching to LangSmith or Langfuse would be abandoning AgentTrace, not upgrading a tracer.

## What this SDK is

~1,000 lines in `sdk/src/agent_trace_sdk/`. Seven modules. One job: emit `span_start` / `span_end` / `span_event` batches to the local backend at `POST /api/v1/ingest/events`.

That wire format works. The backend, UI, and workflow tests already consume it. The SDK tests only check the JSON shape, which is why the lifecycle bugs below survived.

The product (`PRODUCT.md`) is a local-first debugger. The SDK exists to feed *this* stack, not to compete with production observability platforms.

## What's actually broken

Three concrete bugs. All in `Tracer` / `BatchSpanProcessor`. All small.

1. **`with Tracer(...)` does not set the current span.** The docstring says it does. Only `with some_span:` does. Using the span as a second context manager would end it twice. That is why `primo_cleanup.py` calls `set_current_span` by hand.

2. **Export and flush are fire-and-forget.** `_run_async` does `loop.create_task(...)` and never awaits. Fine in a long-lived server. In the CLI, `asyncio.run` closes the loop before those tasks run, so traces never leave the process. That is why the workflow gathers *every* pending task.

3. **The processor does not do what it claims.** `timeout_ms` is never read. There is no retry/backoff despite the docstring. Flush holds the lock during the HTTP call (the comment says it doesn't). None of this is architectural.

There is also a class-level `Tracer._instance` singleton. Fine for one local CLI run. Wrong the moment two tracers overlap. Not urgent for this PoC.

## What is fine

- Event model (`span_start` / `span_end` / `span_event`, parent ids, span types).
- HTTP exporter talking to our ingest API.
- `ContextVar` for current span (per-asyncio-task, which is the right primitive).
- The LangChain callback in `workflows/.../utils/tracing.py`. That is a thin bridge: LangGraph fires run events, we turn a subset into spans. Tests already prove nesting. It does not belong in the workflow forever, but it is not a reason to throw the SDK away.

## Why not LangSmith / Langfuse

They would give a mature LangChain callback and a hosted UI. They would **not** feed AgentTrace.

| | AgentTrace SDK | LangSmith / Langfuse |
|---|---|---|
| Feeds our backend + graph UI | yes | no |
| Local, no account | yes | no (or a second stack to self-host) |
| LangChain auto-instrumentation | we already have a working callback | yes, more complete |
| Production dashboards / evals | not the product | yes |

Using them as the *source of truth* means the local UI, ingest API, and SQLite store become dead weight. Dual-export later is possible if we ever want a production sink. It is not a substitute for a working local tracer.

## What "fix the SDK" means

A few days of work, not a rewrite. After this, `primo_cleanup.py` should look like:

```python
async with Tracer(name="primo_cleanup_pipeline", endpoint=ingest_endpoint()) as _root:
    return await run_pipeline(csv_path)
```

No `set_current_span`, no gather-all-tasks, no swallow-export-errors in the workflow.

Concrete changes:

1. **`__enter__` actually pushes the root as current span** (and restores on `__exit__`).
2. **Async context manager** (`__aenter__` / `__aexit__`) that *awaits* flush and close. Track the SDK's own export tasks; do not wait for unrelated work on the loop.
3. **Honor `timeout_ms`**, or drop it from `BatchConfig` until we do. Flush on span start/end when we want the live graph (`plans/live-run-graph.md`).
4. **Swallow export errors inside the SDK** so a down backend never fails the agent run.
5. **SDK tests that cover lifecycle**, not just JSON shape: current-span on enter, one `span_end` per start, flush actually awaited, CLI-style `asyncio.run` still exports.

Optional later, not blocking:

- Move `AgentTraceCallbackHandler` from workflows into the SDK as the LangChain integration the README already lists as roadmap.
- Replace `Tracer._instance` with an explicit tracer (constructor arg or ContextVar) before anything concurrent.

## Bottom line

The comments in `primo_cleanup.py` are a smell that the **caller** is compensating for a **sync, fire-and-forget tracer**. The model underneath is sound. Fix `Tracer` so entering and leaving it is enough. Do not switch platforms to avoid a ~200-line lifecycle fix.
