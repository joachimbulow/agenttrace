# Workflows

PoC package for agent graphs. The orchestrator is a real LangGraph
`StateGraph`; each agent is an LCEL `Runnable`, and node-level tracing runs
through a LangChain callback handler (see `pipeline/orchestrator.py` and
`agent_trace_sdk.langchain`).

The implemented flow is a **Primo insurance data cleanup** scaffold:
a 6-node pipeline (gate -> enrich -> diagnose -> judge -> determine result
-> correct/save) with two parallel enrichment sub-agents and three parallel
diagnostic paths. It is a quick, deliberately mocked scaffold meant to give
the AgentTrace frontend a realistic, structurally interesting graph to
render -- **not** a real implementation. Every external dependency (DMR,
DB2, staging, HITL) is a clearly marked `# MOCK` stub in `services/`; only
CSV loading is real.

See `docs/workflow_design.md` for the full domain design doc.

```
src/agent_workflows/
  models/schemas.py     shared data contracts (dataclasses) between all nodes
  pipeline/
    orchestrator.py     control-flow ONLY -- wires agent nodes into a StateGraph
    state.py            PipelineState dataclass (imported by agent nodes)
  agents/
    gate/agent.py                 Node 1 -- "do we know this task?"
    enrich/
      dmr_subagent.py             Node 2 -- parallel branch 1
      db2_vehicle_subagent.py     Node 2 -- parallel branch 2
    diagnose/agent.py             Node 3 -- 3 parallel diagnostic paths, converge
    judge/agent.py                Node 4 -- LLM-as-a-judge (mocked), span_type="llm_call"
    determine_result/agent.py     Node 5 -- thresholds verdict into a branch
    correct_validate/agent.py     Node 6, Path A -- apply change + stage
    save_result/agent.py          Node 6, Path B -- HITL / cannot-solve queue
  services/              all EXTERNAL dependencies, MOCKED except csv_loader
    dmr_service.py        DMR reference register (# MOCK)
    db2_service.py        Primo DB2 read access (# MOCK)
    staging_service.py    staging + HITL queue writes (# MOCK)
    csv_loader.py          real (not mocked) local CSV read
  utils/       ingest endpoint config
  workflows/   compose the pipeline into one traced run (primo.py)
data/
  sample_extract.csv     tiny synthetic fixture for local runs
docs/
  workflow_design.md     enriched design doc / domain context
```

## Run

From this directory (AgentTrace backend on `:8000` if you want the UI):

```bash
uv sync
uv run primo-flow                       # uses data/sample_extract.csv
uv run primo-flow data/sample_extract.csv
```

Traces export to `http://localhost:8000/api/v1/ingest/events` unless you set
`AGENTTRACE_ENDPOINT`. If the backend isn't running, export failures do not
fail the workflow (same pattern as before).

## Known open questions / assumptions

Carried forward from the source spec -- **do not resolve these silently**,
they're for the domain/source team to confirm:

1. Whether "Diagnose/Propose: three parallel paths" really means DMR + DB2 +
   rules, or something else. The rules-based third path in
   `agents/diagnose/agent.py` is an assumption made to fill out the count,
   not a confirmed answer.
2. The real Primo CSV extract schema (columns) is not yet finalized.
   `services/csv_loader.py` is schema-tolerant (only requires `policy_id`
   and `task_type`; everything else passes through as a raw dict) --
   adjust once the real schema is known.
3. The confidence threshold in `agents/determine_result/agent.py`
   (`CONFIDENCE_THRESHOLD = 0.75`) is a placeholder, not calibrated.

New assumptions made while adapting the source spec's file layout into
this package's existing conventions:

4. "Conflict" between diagnostic paths (Node 4, judge) is defined narrowly
   as the DMR-driven and DB2-driven proposals disagreeing with each other
   on whether the status is a mismatch. The rules-based path contributes
   to which proposal gets *selected* but is not itself treated as a source
   of conflict, since it checks a different concern (format anomalies)
   than the two source-driven paths. See `agents/judge/agent.py`.
5. The orchestrator processes every record in the CSV concurrently (one
   `asyncio.gather` over all records, each running the full gate -> ... ->
   branch chain), not sequentially -- this doesn't change the per-record
   graph shape, but means the trace for a multi-record CSV shows several
   parallel per-record subtrees under one root span.
6. `pipeline/orchestrator.py` is a LangGraph `StateGraph` that only wires
   agent nodes; `PipelineState` lives in `pipeline/state.py` so nodes can
   import it without a cycle. `enrich` and `diagnose` are each a single
   graph node whose parallel sub-agents are expressed via LCEL
   `RunnableParallel` rather than as separate graph nodes -- see the
   orchestrator docstring for why.
7. `services/staging_service.py`'s "staging area" and "HITL queue" are
   in-memory lists that reset every process run (no persistence) -- fine
   for a scaffold, not representative of a real staging store.
