# Workflows

PoC package for agent graphs. Folder layout is ready for LangGraph; the only
implemented flow is a dummy wait so tracing and `uv` are wired.

```
src/agent_workflows/
  types/       shared state / models
  logic/       pure-ish operations (no tracing)
  nodes/       traced graph nodes (call logic)
  utils/       tracing config, helpers
  workflows/   compose nodes into a run
```

## Run

From this directory (AgentTrace backend on `:8000` if you want the UI):

```bash
uv sync
uv run wait-flow
uv run wait-flow --seconds 2
```

Traces export to `http://localhost:8000/api/v1/ingest/events` unless you set
`AGENTTRACE_ENDPOINT`.
