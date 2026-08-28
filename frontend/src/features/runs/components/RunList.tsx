import { useRuns } from '@/features/runs/hooks/useRuns';
import { RunListItem } from '@/features/runs/components/RunListItem';

export interface RunListProps {
  onSelectRun: (runId: string) => void;
  selectedRunId: string | null;
}

/** Sidebar run picker. A run is a container — pick one to get at its records. ADR-0002. */
export function RunList({ onSelectRun, selectedRunId }: RunListProps) {
  const { data, loading, error, refetch } = useRuns({ limit: 50 });

  if (loading && !data) {
    return <p className="px-3 py-2 text-xs text-muted-foreground">Loading runs…</p>;
  }

  if (error && !data) {
    return (
      <div className="space-y-1.5 px-3 py-2">
        <p className="text-xs text-[oklch(var(--destructive))]">{error.message}</p>
        <button
          type="button"
          onClick={() => refetch()}
          className="text-xs underline underline-offset-2 hover:no-underline"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!data || data.runs.length === 0) {
    return (
      <div className="space-y-1 px-3 py-2">
        <p className="text-xs font-medium">No runs yet</p>
        <p className="text-xs text-muted-foreground">
          Start a traced agent and it will appear here.
        </p>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-0.5 px-1.5 py-1">
      {data.runs.map((run) => (
        <RunListItem
          key={run.id}
          run={run}
          isSelected={selectedRunId === run.id}
          onSelect={() => onSelectRun(run.id)}
        />
      ))}
    </div>
  );
}
