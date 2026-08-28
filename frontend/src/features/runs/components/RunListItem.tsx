import type { Run } from '@/features/runs/types/run';
import { cn } from '@/shared/lib/utils';

export interface RunListItemProps {
  run: Run;
  isSelected: boolean;
  onSelect: () => void;
}

/** No status badge — run-level completion isn't tracked, so every run would lie "running". ADR-0004. */
export function RunListItem({ run, isSelected, onSelect }: RunListItemProps) {
  return (
    <button
      type="button"
      onClick={onSelect}
      aria-current={isSelected}
      className={cn(
        'flex w-full flex-col gap-0.5 rounded-md px-2.5 py-2 text-left transition-colors',
        'hover:bg-accent focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        isSelected && 'bg-accent text-accent-foreground'
      )}
    >
      <span className="truncate text-sm font-medium" title={run.name}>
        {run.name}
      </span>
      <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
        {new Date(run.started_at).toLocaleTimeString()}
      </span>
    </button>
  );
}
