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

- **Agent graph view**: a clean canvas of self-coded cards (not a circuit-board / electrical look, not a pre-drawn workflow definition). The canvas renders **one record** — a single item of work travelling through the pipeline — not a whole run. The graph starts with the first node and grows as the next unit of work spawns. It is fed live by SSE invalidation pings (see `docs/decisions/0001-invalidation-bus-over-event-stream.md`).
- **CSV data view**: a standalone, generic data-grid feature — load any CSV and view it as a clean, sortable/filterable table. Not tied to trace/graph data; a general-purpose table viewer inside the same shell.

Nested agent cards (an Enrich package holding DMR and DB2) and fluid content-driven card resize are deliberately deferred past the first live pass; every span currently renders as a top-level card.

## Positioning

Existing observability tools (Langfuse, LangSmith, etc.) are built for production monitoring — dashboards, metrics, team collaboration — and are heavy, require external services, and aren't optimized for rapid local iteration. AgentTrace is local-first (SQLite, zero external services, works offline), developer-focused (built for understanding behavior during development, not monitoring in prod), and zero-config to start (`make docker-up`).

## Operating Context

- Developer runs their agent code (Python, optionally LangChain) instrumented with the AgentTrace SDK (`@trace_agent_run` decorator or `Tracer` context manager).
- Spans are exported over HTTP to a local AgentTrace backend (FastAPI + async SQLAlchemy + SQLite). The SDK flushes on every `span_start` / `span_end`, so events land within milliseconds rather than after the run finishes.
- Developer opens the web UI (React + TS) and navigates run list → record list → graph canvas. The canvas subscribes to `GET /api/v1/records/{record_id}/events` and refetches that record whenever the backend signals a change.
- Typical loop: run agent → see something wrong → open UI → find the record → watch or inspect the offending card.
- Whole stack usually runs locally via Docker Compose (backend :8000, frontend :3000) or via local dev servers.

## Capabilities and Constraints

- Local-first architecture: SQLite database, no Postgres or external services required.
- Clean/hexagonal backend architecture: domain layer decoupled from infrastructure; repository pattern intended to allow swapping storage later.
- Current UI surfaces: run list, record list, live graph canvas. The trace tree and details panel have been retired.
- Live updates are backed by an in-process invalidation bus and SSE. Single backend process only — running multiple uvicorn workers breaks fan-out, since ingest and the stream would land on different workers.
- **Run-level completion is not tracked.** Every run reads `running` regardless of whether it finished; see `docs/decisions/0004-defer-run-completion.md`. Per-card and per-record status (`running` / `completed` / `error`) are accurate.
- Roadmap items (not implemented): run completion + stale-run sweeping, nested package cards, fluid card resize, timeline/waterfall view, filtering/search across runs, run comparison/diff, evaluation scoring, Postgres backend, JSON export.
- Terminology: see `docs/glossary.md`. The load-bearing distinction is **run** (one execution of an instrumented program — the whole CSV) versus **record** (one item of work through the pipeline — one CSV record). The canvas renders a record; a run is a container you navigate through.

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
