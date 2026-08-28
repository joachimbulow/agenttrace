# ADR-0005: Payload highlights and overlay

**Status:** accepted
**Date:** 2026-08-28
**Amends:** the open "datasheet vs on-card detail" note in `plans/frontend-redesign.md`

## Context

Cards are a fixed tidy-tree cell (`CARD_WIDTH` × `CARD_HEIGHT`). Fluid, content-driven resize
was deferred. Span output still needs to be readable — a judge payload is a nested object, not
a duration chip.

Un-deferring per-card height would mean a two-pass measure and variable-depth bands. A docked
inspector would revive the layout the redesign retired.

## Decision

Keep a **fixed-size card**. Show up to three **highlights** on it. Open the full payload in an
**overlay** on the selected card.

Highlights are generic: unwrap `payload.value` and a one-key envelope, prefer well-known keys
(`status`, `confidence`, `rationale`, …) with a shallow look into nested objects, then leftover
scalars and chips. The overlay is a collapsible tree of the same value. No Primo-specific
views.

## Consequences

- Every card is the same size, including running ones, so the graph does not jump when output
  arrives.
- Full payload is one click away. Neighbours may sit under the overlay; pan still works.
- Preferred keys are a list in `lib/payload.ts`, not a typed `JudgeVerdict` component.
