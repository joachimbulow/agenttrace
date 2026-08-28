// Live readout. No "ended" — a finished run's stream sits idle, and a grey
// disconnected dot would read as failure. ADR-0004.

import { useEffect, useState } from 'react';
import type { StreamStatus } from '@/features/records/hooks/useRecordStream';
import { cn } from '@/shared/lib/utils';

interface StreamIndicatorProps {
  status: StreamStatus;
  lastPingAt: number | null;
}

const LABEL: Record<StreamStatus, string> = {
  idle: 'Not subscribed',
  connecting: 'Connecting',
  live: 'Live',
  reconnecting: 'Reconnecting',
};

const DOT: Record<StreamStatus, string> = {
  idle: 'bg-muted-foreground/50',
  connecting: 'bg-[oklch(var(--warning))] animate-pulse',
  live: 'bg-[oklch(var(--success))]',
  reconnecting: 'bg-[oklch(var(--warning))] animate-pulse',
};

export function StreamIndicator({ status, lastPingAt }: StreamIndicatorProps) {
  const ago = useElapsed(lastPingAt);

  return (
    <div
      className="flex items-center gap-2 text-xs"
      role="status"
      aria-live="polite"
      aria-label={`Stream ${LABEL[status].toLowerCase()}`}
    >
      <span aria-hidden className={cn('h-2 w-2 rounded-full', DOT[status])} />
      <span className="font-medium">{LABEL[status]}</span>
      {ago && (
        <span className="font-mono tabular-nums opacity-70">updated {ago}</span>
      )}
    </div>
  );
}

/** Ticking "0.4s ago" — a slow span looks stalled without it. */
function useElapsed(since: number | null): string | null {
  const [, force] = useState(0);

  useEffect(() => {
    if (since === null) return;
    const timer = window.setInterval(() => force((n) => n + 1), 500);
    return () => window.clearInterval(timer);
  }, [since]);

  if (since === null) return null;

  const seconds = (Date.now() - since) / 1000;
  if (seconds < 1) return 'just now';
  if (seconds < 60) return `${seconds.toFixed(seconds < 10 ? 1 : 0)}s ago`;
  return `${Math.floor(seconds / 60)}m ago`;
}
