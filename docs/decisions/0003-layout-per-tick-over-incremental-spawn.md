# ADR-0003: Lay out the whole tree each tick

**Status:** accepted
**Date:** 2026-08-28
**Amends:** the "Rendering approach" section of `plans/frontend-redesign.md`

## Context

`plans/frontend-redesign.md` instructs: *"spawn-driven, not a one-shot dagre of the full DAG.
Place the new node when it appears; reflow when a card's measured size changes."*

That instruction was written on the assumption that the frontend would receive incremental
events — a `span_start` arrives, you place a node, you never learn about work that hasn't
started. Under that assumption it is correct: you cannot lay out a tree you cannot see.

[ADR-0001](0001-invalidation-bus-over-event-stream.md) changed the assumption. The client now
refetches the complete record subtree on every tick. We see the whole tree, every time.

## Decision

Compute the layout from scratch on every snapshot. New nodes fade in at their computed
position; nodes that shift glide via a CSS transition.

The layout is a tiered tidy-tree, not dagre: depth maps to y, leaves take sequential x
positions, parents centre over their children. A trace is a **tree**, not a DAG — dagre's
value is cycle-breaking and rank assignment over arbitrary graphs, none of which applies. The
implementation is around forty lines and adds no dependency.

Spawn detection comes from diffing snapshots: ids present now and absent from the previous
render (tracked in a ref) get the spawn animation.

## Consequences

- **No collision avoidance to write.** A wide fan-out — `diagnose`'s three parallel paths — is
  laid out correctly by construction. Incremental placement would have needed us to solve this
  by hand, under time pressure, in the exact case the demo shows off.
- **Existing nodes can move** when a sibling appears. The brief's "nothing ever jumps" property
  is traded for "everything is always correctly placed". Animated position changes read as the
  graph organising itself, which is consistent with the growing-canvas intent.
- **Layout must be deterministic** so an unchanged subtree doesn't jitter between ticks.
  Sibling order is by `started_at` then id.
- **Ordering problems vanish entirely.** The server resolved the tree before we saw it, so a
  child can never arrive before its parent. Orphan handling is not a frontend concern.
- Keeps the brief's *intent* — work arriving, cards spawning — while dropping its *mechanism*,
  which was chosen under a constraint that no longer holds.

## Alternatives rejected

- **Incremental placement per the brief** — truer to the letter, but we would own collision
  avoidance and reflow ourselves for no gain now that full snapshots are available.
- **Hybrid: append-only, relayout on collision** — the best-looking result and the most ways
  to be subtly wrong. Revisit if per-tick relayout ever looks unsettled.
