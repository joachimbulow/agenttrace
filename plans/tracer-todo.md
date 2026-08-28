# Tracer TODOs

Known gaps in `agent_trace_sdk.Tracer` / `BatchSpanProcessor`, found while reviewing
how `workflows/pipeline/orchestrator.py` shares one `Tracer` + one
`AgentTraceCallbackHandler` across concurrently-processed CSV records
(`asyncio.gather` over `_run_record`). Not urgent for the current single-tracer,
single-process batch job, but load-bearing the moment either assumption below stops
holding.

## 1. `Tracer._instance` is a bare class-level singleton, not passed explicitly

`Tracer.set_instance`/`get_instance` (`sdk/src/agent_trace_sdk/tracer.py:64-80`) store the
active tracer as a plain class attribute with no stack/refcount. `__enter__` does
`Tracer.set_instance(self)`, `__exit__` unconditionally does `Tracer.set_instance(None)`.

Consumers that assume "exactly one active `Tracer` in this process":
- `AgentTraceCallbackHandler.on_chain_start` (`workflows/src/agent_workflows/utils/tracing.py:124`)
- `trace_span` sync/async wrappers (`sdk/src/agent_trace_sdk/decorators.py:106,120`)
- `trace_agent_run` decorator, constructs its own `Tracer` (`decorators.py:44,55`)

Today this is safe: only `workflows/primo_cleanup.py:30` constructs a `Tracer` in
production code, and nothing nests or overlaps it. It breaks the moment two `Tracer`
contexts are ever active concurrently in one process (e.g. running two pipeline jobs
in the same worker, a future service handling concurrent requests, or a nested
`trace_agent_run` inside a `with Tracer(...)` block) — the second `__enter__` clobbers
the first's global instance, and the first `__exit__` tears it down under the second's
still-running spans.

**Fix direction:** pass the `Tracer` (or at least its `run_id`) explicitly through the
call chain instead of a class-level singleton — e.g. thread it through LangGraph's
`config` alongside `callbacks`, or make `AgentTraceCallbackHandler` take a `Tracer` in
its constructor per pipeline run instead of resolving `Tracer.get_instance()` per
callback. Same concern applies to the `_current_span`/`_current_run_id` ContextVars
(`sdk/src/agent_trace_sdk/context.py`) — safer than the class singleton since they're
per-asyncio-task, but every consumer still assumes a single unambiguous "current"
value with no representation of multiple concurrent runs.

## 2. No timeout-based flush or orphaned-span handling

`BatchConfig.timeout_ms` (`processor.py:29`, default 5000) is defined but never read
anywhere in `BatchSpanProcessor` — no timer, no background task. The only flush
triggers are size (`len(self._events) >= max_size`) and explicit `flush()`/`close()`
calls. Effects:

- A span that gets a `span_start` event but never a `span_end` (process crash, an
  exception path that bypasses `on_chain_end`/`on_chain_error`, or the callback
  handler itself raising) sits open forever on the backend — nothing locally expires
  it or force-closes it.
- `AgentTraceCallbackHandler._parents`/`_spans` (`workflows/.../tracing.py:92-93`) would
  leak entries for such a run for the lifetime of the process (handler is a long-lived
  singleton). Not observed in current code paths, but nothing guards against it.
- Events sitting in the in-memory deque (`self._events`, maxlen 10k) at crash time are
  lost outright — cleared only *after* a successful export, no WAL/persistence.

**Fix direction:** add a real timeout-based flush (background task or checked on
`add_event`) so `timeout_ms` actually does something, and consider a local
force-close/expire path for spans whose run_id hasn't reported `on_chain_end` within
some bound, so a crashed or hung run doesn't leave permanently-open spans on the
backend.

## 3. Exporter has no retry/backoff despite claiming to

`processor.py:40`'s docstring claims "Retry logic with exponential backoff," but
`_flush_internal` just re-raises `ExportError` once on failure — no retry loop exists
anywhere in `processor.py` or `exporter.py`. `HTTPExporter` does a single POST with a
plain request timeout (`exporter.py:18,42`), no retry/backoff. Either implement the
retry logic the docstring describes, or correct the docstring.
