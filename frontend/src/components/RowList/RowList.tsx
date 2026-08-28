// Rows of the selected run. A row is one item of work through the
// pipeline and is what the canvas renders.
// See docs/decisions/0002-row-as-unit-of-observation.md.

import { RowStatus, type RowSummary } from '../../types';
import { cn } from '../../lib/utils';

export interface RowListProps {
  rows: RowSummary[];
  runSelected: boolean;
  loading: boolean;
  error: Error | null;
  selectedRowId: string | null;
  onSelectRow: (rowId: string) => void;
}

const STATUS_DOT: Record<RowStatus, string> = {
  [RowStatus.RUNNING]: 'bg-[oklch(var(--info))] animate-pulse',
  [RowStatus.COMPLETED]: 'bg-[oklch(var(--success))]',
  [RowStatus.ERROR]: 'bg-[oklch(var(--destructive))]',
};

export function RowList({
  rows,
  runSelected,
  loading,
  error,
  selectedRowId,
  onSelectRow,
}: RowListProps) {
  if (!runSelected) {
    return <p className="px-3 py-2 text-xs text-muted-foreground">Select a run first.</p>;
  }

  if (error) {
    return (
      <p className="px-3 py-2 text-xs text-[oklch(var(--destructive))]">{error.message}</p>
    );
  }

  if (loading && rows.length === 0) {
    return <p className="px-3 py-2 text-xs text-muted-foreground">Loading rows…</p>;
  }

  if (rows.length === 0) {
    // A row can't exist before its first span, so an in-flight run legitimately
    // shows nothing for a moment.
    return (
      <p className="px-3 py-2 text-xs text-muted-foreground">
        No rows have started yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 px-1.5 py-1">
      {rows.map((row) => (
        <button
          key={row.row_id}
          type="button"
          onClick={() => onSelectRow(row.row_id)}
          aria-current={selectedRowId === row.row_id}
          className={cn(
            'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors',
            'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            selectedRowId === row.row_id && 'bg-accent text-accent-foreground'
          )}
        >
          <span
            aria-hidden
            className={cn('h-2 w-2 shrink-0 rounded-full', STATUS_DOT[row.status])}
          />
          {/* policy_id first: record_id is an opaque UUID, the policy is what
              a person recognises. Falls back through both for a bare-SDK run. */}
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-xs" title={row.name}>
              {row.policy_id ?? row.record_id ?? row.name}
            </span>
            <span className="block truncate text-[11px] text-muted-foreground">
              {row.status}
            </span>
          </span>
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
            {row.node_count}
          </span>
        </button>
      ))}
    </div>
  );
}
