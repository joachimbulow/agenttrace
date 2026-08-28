# Frontend redesign: graph view + CSV view (handoff)

> **PARTIALLY SUPERSEDED.** The visual language here — quiet canvas, self-coded cards, spawn as
> work arrives, no library node chrome — still stands and is what got built. Three points were
> amended:
>
> - `docs/decisions/0003-layout-per-tick-over-incremental-spawn.md` — "do not dagre the full
>   DAG, place nodes incrementally" is reversed. The client receives complete snapshots, so the
>   whole tree is laid out each tick and positions animate.
> - `docs/decisions/0002-row-as-unit-of-observation.md` — the canvas renders **one row**, not a
>   run. Navigation is run list → row list → canvas; `RunList` survives rather than being retired.
> - **Nested package cards and fluid content-driven resize are deferred.** Every span currently
>   renders as a top-level card. The "Nested agents" and "Fluid size" sections below describe a
>   later pass, not shipped behaviour.
>
> The Tailwind/shadcn migration flagged as a prerequisite has landed.

**Status:** design direction confirmed — not started
**Goal:** replace the current 3-pane trace debugger (run list / trace tree / details panel) with two new views — a growing agent-card graph on a clean canvas, and a standalone CSV data-grid.
**Related:** [live-run-graph.md](./live-run-graph.md) is the backend/streaming plan (SSE, event bus) that feeds this graph. This document is the *visual/UX* contract. They converge on the same interaction: the canvas starts empty-of-work, the first node appears, and further nodes (and nested agent cards) spawn as the run proceeds.

## Product context (see `PRODUCT.md` at repo root for full detail)

- Primary user: a solo AI/agent developer debugging locally, who also uses the UI to demo agent behavior to clients — so it needs to read as professional and technical, not a personal scratchpad.
- Stack: React + Vite + TS, migrating to Tailwind + shadcn/ui (in progress separately — confirm that migration has landed before building on top of it).
- Product direction: AgentTrace is moving from a post-hoc trace debugger toward a real-time agent visualization framework. This redesign is step one of that move on the frontend.

## Scope

- **Full replacement**, not a restyle: the existing run-list/trace-tree/details-panel layout is retired. Nothing from it carries over as-is.
- **Two new views:**
  1. **Agent graph view** (primary, gets the design depth) — a clean canvas of self-coded cards. The graph is the *execution as it happens*, not a pre-drawn workflow definition. Nodes appear when work starts; a node may contain nested agent cards (e.g. Enrich contains DMR and DB2).
  2. **CSV data view** (secondary, standard pattern) — a generic, standalone data-grid: load any CSV, view as a clean sortable/filterable table. Not wired to trace or graph data.
- **Iteration boundary:** first pass may still be driven by a completed-run snapshot (backend does not stream yet; see [live-run-graph.md](./live-run-graph.md)). Build the view *as if it were live*: one node, then spawn, then nested cards, then fluid resize. Do not ship a fully laid-out static DAG that has to be thrown away when SSE lands. Mock or replay spawn order if the API only has a finished tree.

## Visual direction: Clean canvas, growing cards

Not a circuit board, not copper traces, not silkscreen, not an electrical metaphor. The canvas is quiet. The cards are the product.

Chosen over a PCB/schematic treatment because the thing we want to show is work arriving — a card that did not exist a moment ago, then fills, then may grow children — not a board that was always there and merely lights up.

- **World:** an empty, calm surface. React Flow is a dumb viewport (pan/zoom only). No default dot-grid background, no minimap, no attribution, no built-in controls until a later pass proves they are needed. Orthogonal edges, visually quiet — connectors, not decoration.
- **Cards:** always self-coded React (shadcn + Tailwind). Library node chrome is not used. Each card shows reasoning / output / status. Values (durations, IDs, raw output) are monospace; labels are the surrounding UI type.
- **Growth:** the canvas starts with no work-nodes. The first node spawns (the root). As the next unit of work starts, a new node is added and an orthogonal edge is drawn to it. Unspawned work is absent, not drawn idle.
- **Nested agents:** a node is a package that can contain other cards. Example: Enrich spawns as one node; when DMR and DB2 start, cards appear *inside* Enrich, not as extra top-level graph nodes. Nested cards follow the same spawn / status / expand rules recursively.
- **Fluid size:** a node’s width/height follow its content. Streaming text, extra nested cards, or an expanded reasoning block must resize the card and reflow the canvas so neighbors do not overlap. Size is measured from the card, not fixed in the graph schema.
- **Status** (once a card exists): `running` / `completed` / `error`. Do not pre-render `idle` placeholders for work that has not started. A parent package can stay `running` while children are still spawning.
- **CSV view treatment:** same quiet, professional language — clean table, monospace figures, no thematic overlay. Standard sortable/filterable grid.
- **Motion:** smooth for spawn, nested-insert, and fluid resize (the growth *is* the signature). Status changes can be more immediate. No pulse-along-a-trace, no glow-as-power metaphors.
- **Honest risk:** a generic React Flow demo (default nodes, default grid, default edges) will look like every other agent graph. The differentiator is the cards and the spawn/reflow behavior. If those are weak, hiding the library chrome will not save it.

## Rendering approach (resolved)

- **Canvas:** React Flow (xyflow). Custom node types only; custom orthogonal edges; hide default background, controls, and minimap.
- **Cards:** project components, not library nodes. Recursive render inside a package (`PackageCard` → child `AgentCard`s).
- **Layout:** spawn-driven, not a one-shot dagre of the full DAG. Place the new node when it appears; reflow when a card’s measured size changes. Auto-layout of an unknown graph is a later problem, not this pass.
- **Streaming:** patch card `data` in place (status, tokens, duration). Stable ids. Do not remount the canvas on each event. Do not relayout the whole graph on a text patch — only when size actually changed.

## States and ranges

- Graph view card states: running / completed / error; page-level: no-data / loading / empty (no run selected). Canvas-with-no-nodes-yet is a valid live state (run started, root not yet spawned), distinct from empty (no run).
- Content scale: modest node counts and payload sizes (confirmed as the realistic case). Nested packages are the way wide fan-out (Enrich → two sub-agents, Diagnose → three paths) stays readable, rather than exploding sibling count.
- CSV view states: empty (no file loaded), loading, loaded-with-data, malformed-CSV error.

## Open decisions for whoever builds this

- **Datasheet vs on-card detail:** whether selecting a card opens a docked panel or the card itself expands to show full reasoning/output. Default to on-card expansion (fluid size already requires this); add a dock only if density demands it.
- **Sequencing with the Tailwind/shadcn migration:** check whether that's landed before starting; building on the old plain-CSS setup means redoing styling twice.
- **DESIGN.md:** doesn't exist yet. It gets written from the built result once this ships — don't hand-author a rulebook ahead of the build.

## How to pick this up with Claude Code + the Impeccable skill

This brief was produced by `/impeccable shape` and then revised away from a circuit-board world toward a clean growing-card canvas. To build it:

1. Confirm `PRODUCT.md` at the repo root still matches (graph view is growing cards on a clean canvas, not a static definition DAG).
2. Ask Claude to build against this brief directly, e.g.: *"Build the agent graph view from plans/frontend-redesign.md: clean canvas, self-coded cards, spawn as the run proceeds, nested agent cards inside packages."* Point it at this file plus `PRODUCT.md`.
3. The two views can go to two different sessions/agents in parallel since they don't share state — just make sure both are pointed at this same document so they don't drift into different visual languages.
4. After the graph view is built, do the same for the CSV view, then run `/impeccable polish` and, once satisfied, let the build write `DESIGN.md` from what actually shipped (Claude/Impeccable does this automatically at finish on a new visual world).
5. For wiring the graph view to real-time data, hand off to [live-run-graph.md](./live-run-graph.md)'s implementation slices — that's the backend/streaming half of this same feature.
