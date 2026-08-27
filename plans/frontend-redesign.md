# Frontend redesign: graph view + CSV view (handoff)

**Status:** design direction confirmed — not started
**Goal:** replace the current 3-pane trace debugger (run list / trace tree / details panel) with two new views — a LangGraph node/edge graph with detail cards, and a standalone CSV data-grid — built on a committed "Circuit Board Schematic" visual direction.
**Related:** [live-run-graph.md](./live-run-graph.md) is the backend/streaming plan for making the graph update in real time. This document is the *visual/UX* direction for the graph and CSV views; that document is the *plumbing* (SSE, event bus, React Flow wiring) to make it live. They should converge: this redesign's graph view is the UI [live-run-graph.md](./live-run-graph.md) is building the data pipe for.

## Product context (see `PRODUCT.md` at repo root for full detail)

- Primary user: a solo AI/agent developer debugging locally, who also uses the UI to demo agent behavior to clients — so it needs to read as professional and technical, not a personal scratchpad.
- Stack: React + Vite + TS, migrating to Tailwind + shadcn/ui (in progress separately — confirm that migration has landed before building on top of it).
- Product direction: AgentTrace is moving from a post-hoc trace debugger toward a real-time agent visualization framework. This redesign is step one of that move on the frontend.

## Scope

- **Full replacement**, not a restyle: the existing run-list/trace-tree/details-panel layout is retired. Nothing from it carries over as-is.
- **Two new views:**
  1. **Agent graph view** (primary, gets the design depth) — renders the LangGraph node/edge topology itself (the workflow definition, not just executed spans — a "graph node" is a distinct concept from a "span" in `PRODUCT.md`'s terminology). Each node renders as a card showing reasoning/output/status.
  2. **CSV data view** (secondary, standard pattern) — a generic, standalone data-grid: load any CSV, view as a clean sortable/filterable table. Not wired to trace or graph data.
- **Iteration boundary:** this pass ships **static/raw-data rendering only**. No live streaming yet — the backend doesn't push updates (SDK batches and posts after a run completes; see [live-run-graph.md](./live-run-graph.md) for the plan to change that). Build the graph view's components so a "live/powered" state has somewhere to attach later; don't build a dead end that has to be re-architected when streaming lands.

## Visual direction: Circuit Board Schematic

Chosen over three alternates (a transit-diagram system, a literal IDE-debugger call-stack read, and the plain-dashboard category default) because it gives both views one grammar that fits their actual shapes: a node/edge graph maps directly onto a PCB's components-and-traces, and a data table maps directly onto a bill-of-materials list.

- **World:** each LangGraph node is a component package on a board; edges are copper traces routed at right angles only (never diagonal); a docked "datasheet" card sits on/beside each package with its live detail.
- **Palette:** dark PCB-green or matte charcoal board as ground, copper/gold as the trace material, silkscreen-white for labels. Committed-to-full palette: copper is the dominant accent; status gets named secondary colors — running = warm amber glow, error = red trace break, idle = dim/unlit copper.
- **Type:** silkscreen/stencil-adjacent caps for node labels and section headers; monospace for every data value (durations, IDs, raw output).
- **Signature interaction:** selecting a node routes a lit pulse along its incoming edge before the datasheet card expands. This is authored now as a one-shot animation — it's the exact seam where live streaming plugs in later (a running node stays "powered," the pulse repeats while active).
- **CSV view treatment:** same board/type system, rendered as a component BOM table — silkscreen header row, monospace figures, parts-list row striping. Standard sortable/filterable grid; no bespoke interaction beyond the shared type/color system.
- **Motion grammar:** instant, un-eased toggles for binary state (a trace is lit or it isn't — no soft fades); smooth motion reserved for the one signature trace-pulse.
- **Honest risk:** circuit-board/PCB aesthetics are a fairly saturated look in AI-tool UI generally. The differentiator has to be full commitment to real schematic conventions (right-angle routing only, real component-package proportions, actual silkscreen typography) — not a green-and-copper skin over a generic node-graph library's default look.

## States and ranges

- Graph view node states: idle / running / completed / error (mirrors existing `RunStatus`); page-level: no-data / loading / empty (no run/graph selected).
- Content scale: design for modest node counts and payload sizes (confirmed as the realistic case), but keep the "idle branches recede to dim copper" rule so a wide graph still degrades gracefully.
- CSV view states: empty (no file loaded), loading, loaded-with-data, malformed-CSV error.

## Open decisions for whoever builds this

- **Graph rendering approach:** not resolved in this brief. [live-run-graph.md](./live-run-graph.md) already recommends React Flow (xyflow) + dagre for the live-graph plumbing — worth defaulting to the same library here rather than picking a second one, but confirm it can carry the right-angle-trace, component-card visual language before committing.
- **Sequencing with the Tailwind/shadcn migration:** check whether that's landed before starting; building on the old plain-CSS setup means redoing styling twice.
- **DESIGN.md:** doesn't exist yet. It gets written from the built result once this ships — don't hand-author a rulebook ahead of the build.

## How to pick this up with Claude Code + the Impeccable skill

This brief was produced by `/impeccable shape`. To build it:

1. Confirm `PRODUCT.md` at the repo root still matches (it now includes the graph/CSV view capabilities this brief assumes).
2. Ask Claude to build against this brief directly, e.g.: *"Build the agent graph view from plans/frontend-redesign.md, Circuit Board Schematic direction."* Point it at this file plus `PRODUCT.md`.
3. The two views can go to two different sessions/agents in parallel since they don't share state — just make sure both are pointed at this same document so they don't drift into different visual languages.
4. After the graph view is built, do the same for the CSV view, then run `/impeccable polish` and, once satisfied, let the build write `DESIGN.md` from what actually shipped (Claude/Impeccable does this automatically at finish on a new visual world).
5. For wiring the graph view to real-time data later, hand off to [live-run-graph.md](./live-run-graph.md)'s implementation slices — that's the backend/streaming half of this same feature.
