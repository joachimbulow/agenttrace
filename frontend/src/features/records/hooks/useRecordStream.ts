// Live subscription. Pings mean "this record changed, refetch it" — no span data.
// See docs/decisions/0001-invalidation-bus-over-event-stream.md.

import { useEffect, useRef, useState } from 'react';
import { recordEventsUrl } from '@/features/records/api/recordsApi';
import type { RecordInvalidation } from '@/features/records/types/record';

/** No `ended` yet — a finished run's stream just sits idle. ADR-0004. */
export type StreamStatus = 'idle' | 'connecting' | 'live' | 'reconnecting';

export interface RecordStream {
  status: StreamStatus;
  /** Bumps on every ping. Anything that should refetch depends on this. */
  rev: number;
  /** When the record last actually changed, for the "updated Ns ago" readout. */
  lastPingAt: number | null;
}

/** Mirrors `presentation/routers/records.py:KEEPALIVE_SECONDS`. */
const HEARTBEAT_MS = 10_000;
/** EventSource won't notice a dead socket; 2.5 missed heartbeats = stale. */
const STALE_AFTER_MS = HEARTBEAT_MS * 2.5;

export function useRecordStream(recordId: string | null): RecordStream {
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [rev, setRev] = useState(0);
  const [lastPingAt, setLastPingAt] = useState<number | null>(null);

  // Survives EventSource's own retries — a retry isn't a fresh subscription.
  const hasConnected = useRef(false);
  const lastFrameAt = useRef<number>(0);

  useEffect(() => {
    if (!recordId) {
      setStatus('idle');
      setRev(0);
      setLastPingAt(null);
      return;
    }

    hasConnected.current = false;
    lastFrameAt.current = Date.now();
    setStatus('connecting');
    setRev(0);
    setLastPingAt(null);

    const source = new EventSource(recordEventsUrl(recordId));

    source.onopen = () => {
      hasConnected.current = true;
      lastFrameAt.current = Date.now();
      setStatus('live');
    };

    source.onmessage = (event) => {
      let ping: RecordInvalidation;
      try {
        ping = JSON.parse(event.data);
      } catch {
        return;
      }

      hasConnected.current = true;
      lastFrameAt.current = Date.now();
      setStatus('live');

      // Heartbeats prove liveness; they must not reset "updated Ns ago".
      if (!ping.heartbeat) setLastPingAt(Date.now());

      setRev((current) => (ping.rev > current ? ping.rev : current));
    };

    source.onerror = () => {
      // EventSource reconnects itself. Don't say `reconnecting` until we've opened once.
      setStatus(hasConnected.current ? 'reconnecting' : 'connecting');
    };

    // Catches silent death that `onerror` never fires for.
    const watchdog = window.setInterval(() => {
      if (Date.now() - lastFrameAt.current > STALE_AFTER_MS) {
        setStatus((current) => (current === 'live' ? 'reconnecting' : current));
      }
    }, HEARTBEAT_MS / 2);

    return () => {
      window.clearInterval(watchdog);
      source.close();
    };
  }, [recordId]);

  return { status, rev, lastPingAt };
}
