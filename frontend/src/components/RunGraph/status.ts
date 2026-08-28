// Card status, derived from the snapshot. Nothing is persisted server-side
// — see docs/decisions/0004-defer-run-completion.md.

import type { TraceNode } from '../../types';

export type CardStatus = 'running' | 'completed' | 'error';

/**
 * A card's status.
 *
 * `error` is the reason the row endpoint carries event payloads inline:
 * a failure exists only as an `error` event on the span, not as a column.
 */
export function cardStatus(node: TraceNode): CardStatus {
  if (node.events.some((event) => event.event_type === 'error')) {
    return 'error';
  }
  return node.ended_at ? 'completed' : 'running';
}

export function formatDuration(ms: number | null): string | null {
  if (ms === null) return null;
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(2)}s`;
  const minutes = Math.floor(ms / 60_000);
  return `${minutes}m ${Math.round((ms % 60_000) / 1000)}s`;
}
