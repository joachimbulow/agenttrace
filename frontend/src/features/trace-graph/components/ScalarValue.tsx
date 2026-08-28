import { formatScalar, isScalar } from '@/features/trace-graph/lib/payload';
import { booleanTone, isUnitInterval, unitIntervalOklch } from '@/features/trace-graph/lib/scalarTone';
import { cn } from '@/shared/lib/utils';

const BOOL_PILL: Record<'true' | 'false', string> = {
  true: 'bg-[oklch(var(--success-bg))] text-[oklch(var(--success-fg))]',
  false: 'bg-[oklch(var(--danger-bg))] text-[oklch(var(--danger-fg))]',
};

export function ScalarValue({
  value,
  maxChars,
  wrap = false,
}: {
  value: unknown;
  maxChars?: number;
  wrap?: boolean;
}) {
  if (typeof value === 'boolean') {
    const label = formatScalar(value, maxChars);
    return (
      <span
        className={cn(
          'inline-flex shrink-0 rounded px-1 py-px font-mono text-[10px] uppercase tracking-wide',
          BOOL_PILL[booleanTone(value)]
        )}
      >
        {label}
      </span>
    );
  }

  const text = isScalar(value) ? formatScalar(value, maxChars) : String(value);
  if (isUnitInterval(value)) {
    return (
      <span
        className="font-mono text-[11px] tabular-nums"
        style={{ color: unitIntervalOklch(value) }}
      >
        {text}
      </span>
    );
  }

  return (
    <span
      className={cn(
        'font-mono text-[11px] tabular-nums text-card-foreground',
        wrap ? 'min-w-0 whitespace-pre-wrap break-words' : 'min-w-0 truncate'
      )}
      title={wrap ? undefined : text}
    >
      {text || '""'}
    </span>
  );
}
