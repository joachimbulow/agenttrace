// Records of the selected run. A record is one item of work through the
// pipeline and is what the canvas renders.
// See docs/decisions/0002-record-as-unit-of-observation.md.

import { RecordStatus, type RecordSummary } from '../../types';
import { cn } from '../../lib/utils';

export interface RecordListProps {
  records: RecordSummary[];
  runSelected: boolean;
  loading: boolean;
  error: Error | null;
  selectedRecordId: string | null;
  onSelectRecord: (recordId: string) => void;
}

const STATUS_DOT: Record<RecordStatus, string> = {
  [RecordStatus.RUNNING]: 'bg-[oklch(var(--info))] animate-pulse',
  [RecordStatus.COMPLETED]: 'bg-[oklch(var(--success))]',
  [RecordStatus.ERROR]: 'bg-[oklch(var(--destructive))]',
};

export function RecordList({
  records,
  runSelected,
  loading,
  error,
  selectedRecordId,
  onSelectRecord,
}: RecordListProps) {
  if (!runSelected) {
    return <p className="px-3 py-2 text-xs text-muted-foreground">Select a run first.</p>;
  }

  if (error) {
    return (
      <p className="px-3 py-2 text-xs text-[oklch(var(--destructive))]">{error.message}</p>
    );
  }

  if (loading && records.length === 0) {
    return <p className="px-3 py-2 text-xs text-muted-foreground">Loading records…</p>;
  }

  if (records.length === 0) {
    // A record can't exist before its first span, so an in-flight run legitimately
    // shows nothing for a moment.
    return (
      <p className="px-3 py-2 text-xs text-muted-foreground">
        No records have started yet.
      </p>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 px-1.5 py-1">
      {records.map((record) => (
        <button
          key={record.id}
          type="button"
          onClick={() => onSelectRecord(record.id)}
          aria-current={selectedRecordId === record.id}
          className={cn(
            'flex w-full items-center gap-2 rounded-md px-2.5 py-2 text-left transition-colors',
            'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
            selectedRecordId === record.id && 'bg-accent text-accent-foreground'
          )}
        >
          <span
            aria-hidden
            className={cn('h-2 w-2 shrink-0 rounded-full', STATUS_DOT[record.status])}
          />
          {/* policy_id first: record_id is an opaque UUID, the policy is what
              a person recognises. Falls back through both for a bare-SDK run. */}
          <span className="min-w-0 flex-1">
            <span className="block truncate font-mono text-xs" title={record.name}>
              {record.policy_id ?? record.record_id ?? record.name}
            </span>
            <span className="block truncate text-[11px] text-muted-foreground">
              {record.status}
            </span>
          </span>
          <span className="shrink-0 font-mono text-[11px] tabular-nums text-muted-foreground">
            {record.node_count}
          </span>
        </button>
      ))}
    </div>
  );
}
