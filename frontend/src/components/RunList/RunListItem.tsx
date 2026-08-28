import type { Run } from '../../types';
import { cn } from '../../lib/utils';

export interface RunListItemProps {
  run: Run;
  isSelected: boolean;
  onSelect: () => void;
}

/**
 * Compact run entry for the sidebar.
 *
 * Deliberately shows no status badge: run-level completion isn't tracked,
 * so every run reports `running` forever and the badge would be a lie on
 * every run. See docs/decisions/0004-defer-run-completion.md.
 */
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
