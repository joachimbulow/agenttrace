import type { Highlight } from '@/features/trace-graph/lib/payload';
import { ScalarValue } from '@/features/trace-graph/components/ScalarValue';
import { cn } from '@/shared/lib/utils';

export function PayloadHighlights({ rows }: { rows: Highlight[] }) {
  if (rows.length === 0) return null;

  return (
    <ul className="flex min-h-0 flex-1 flex-col justify-center gap-0.5">
      {rows.map((row) => (
        <li key={row.key} className="flex min-w-0 items-center gap-1.5">
          {row.kind === 'chip' ? (
            <span
              className={cn(
                'truncate rounded px-1 py-px font-mono text-[10px]',
                'bg-secondary text-secondary-foreground'
              )}
            >
              {row.display}
            </span>
          ) : (
            <>
              <span className="shrink-0 font-mono text-[10px] text-muted-foreground">
                {row.key}
              </span>
              <ScalarValue value={row.value} />
            </>
          )}
        </li>
      ))}
    </ul>
  );
}
