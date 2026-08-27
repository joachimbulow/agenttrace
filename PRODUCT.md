# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Stack

React + Vite + TypeScript. Tailwind and shadcn/ui are being added (in progress, by other agents) as the styling/component foundation going forward — design work should target that combination rather than the current plain-CSS (`App.css`) approach.

## Users

Primary user: a solo AI/agent developer building an LLM or agent app locally. They reach for AgentTrace right after a run, to figure out why their agent misbehaved — an infinite loop, an unexpected tool call, or a confusing/wrong output. Secondary, confirmed use: the same developer sometimes uses the UI to showcase agent behavior to a client, so the surface also has to read as professional and demo-worthy, not just a personal debug scratchpad.

## Product Purpose

AgentTrace gives step-by-step visibility into AI agent execution during local development: it captures spans, tool calls, prompts, and responses via a Python SDK, stores them locally (SQLite, no external services). Success means a developer can go from "my agent did something wrong" to "here's the exact span/prompt/response that caused it" quickly, without standing up production observability infrastructure.

The product is moving from a post-hoc trace debugger toward a real-time agent visualization framework. The frontend is being rebuilt around two primary views, replacing the original run-list/trace-tree/details-panel layout:

- **Agent graph view**: a clean canvas of self-coded cards (not a circuit-board / electrical look, not a pre-drawn workflow definition). The graph starts with the first node and grows as the next unit of work spawns; nodes fluidly expand to fit their content. A node can contain nested agent cards (e.g. an Enrich package holding DMR and DB2). First iteration may still be driven by a completed-run snapshot — the backend does not yet stream, it batches and posts after the run completes — but the view is built as spawn-and-grow, not as a static fully-laid-out DAG.
- **CSV data view**: a standalone, generic data-grid feature — load any CSV and view it as a clean, sortable/filterable table. Not tied to trace/graph data; a general-purpose table viewer inside the same shell.

Both views ship iteratively: the card/canvas model is the first pass; real SSE/live push is the next (see `plans/live-run-graph.md`). Design and build should leave room for that trajectory rather than treating the first pass as a static showcase.

## Positioning

Existing observability tools (Langfuse, LangSmith, etc.) are built for production monitoring — dashboards, metrics, team collaboration — and are heavy, require external services, and aren't optimized for rapid local iteration. AgentTrace is local-first (SQLite, zero external services, works offline), developer-focused (built for understanding behavior during development, not monitoring in prod), and zero-config to start (`make docker-up`).

## Operating Context

- Developer runs their agent code (Python, optionally LangChain) instrumented with the AgentTrace SDK (`@trace_agent_run` decorator or `Tracer` context manager).
- Spans are batched and exported over HTTP to a local AgentTrace backend (FastAPI + async SQLAlchemy + SQLite).
- Developer opens the web UI (React + TS) to browse: a run list (name, timestamps, duration, status), a trace tree (expand/collapse spans: `agent_run`, `step`, `tool_call`, `llm_call`), and a details panel (span type, timing, attributes, events — prompts/responses/errors).
- Typical loop: run agent → see something wrong → open UI → drill into the trace tree → inspect the offending span's details.
- Whole stack usually runs locally via Docker Compose (backend :8000, frontend :3000) or via local dev servers.

## Capabilities and Constraints

- Local-first architecture: SQLite database, no Postgres or external services required.
- Clean/hexagonal backend architecture: domain layer decoupled from infrastructure; repository pattern intended to allow swapping storage later.
- Current implemented UI surfaces (being replaced): run list, trace tree, details panel.
- New frontend direction (in progress): an agent graph view (clean canvas, self-coded cards that spawn as work starts, nested agent cards inside packages) and a standalone CSV data-grid view. First iteration may replay a finished tree as spawn-and-grow; live streaming is planned but not yet backed by the API (SDK currently batches and posts after a run completes — no WebSocket/SSE push exists today).
- Roadmap items (not implemented): live streaming updates to the graph view, timeline/waterfall view, filtering/search across runs, run comparison/diff, evaluation scoring, Postgres backend, JSON export.
- Terminology: "run" (a traced agent execution), "span" (a unit of work within a run: `agent_run`, `step`, `tool_call`, `llm_call`), "event" (custom data attached to a span, e.g. `input`/`output`/`error`), "attribute" (key-value metadata on a span), "graph node" (a card on the canvas — appears when that work starts; may be a package containing nested agent cards). Distinct from a span, which is the recorded execution unit that *feeds* the card.

## Brand Commitments

Name: AgentTrace. No logo, color palette, or typography has been decided yet. Confirmed tone constraint: the product must read as professional and a bit technical — it is also used to showcase agent behavior to clients, not only for the developer's own private debugging.

## Evidence on Hand

No customer testimonials, case studies, press, or benchmark data exist. Do not fabricate any. Star history badge on the README is the only external "social proof" element present, and it is auto-generated (not a claim to preserve or extend).

## Product Principles

1. Local-first, zero-config: never introduce a requirement for external services or accounts to use the core debugging flow.
2. Optimize for the "something went wrong, find out why" loop — the growing card graph is the product; everything else supports that path.
3. Developer tool, not a dashboard: prioritize signal density and speed over decoration, while still reading as professional enough to demo to a client.
4. Don't imply capabilities from the roadmap (timeline view, run comparison, evaluations) as if they exist today.

## Accessibility & Inclusion

No product-specific accessibility requirement has been established beyond standard web accessibility practice.
