// Live subscription to a row's invalidation stream.
//
// The stream carries no span data — only "this row changed, refetch it".
// See docs/decisions/0001-invalidation-bus-over-event-stream.md.

import { useEffect, useRef, useState } from 'react';
import { rowEventsUrl } from '../api/client';
import type { RowInvalidation } from '../types';

/**
 * Two states, not three. There is no `ended`: run completion isn't tracked
 * yet, so a finished run's stream simply sits idle emitting keepalives.
 * See docs/decisions/0004-defer-run-completion.md.
 */
export type StreamStatus = 'idle' | 'connecting' | 'live' | 'reconnecting';

export interface RowStream {
  status: StreamStatus;
  /** Bumps on every ping. Anything that should refetch depends on this. */
  rev: number;
  /** When the row last actually changed, for the "updated Ns ago" readout. */
  lastPingAt: number | null;
}

/**
 * Server heartbeat interval, mirrored from
 * `presentation/routers/rows.py:KEEPALIVE_SECONDS`.
 */
const HEARTBEAT_MS = 10_000;

/**
 * How long without any frame before we stop claiming to be live.
 *
 * `EventSource` never times out a silent socket, so if the backend process
 * dies without closing the TCP connection the browser notices nothing and
 * the indicator would read "Live" indefinitely. Two and a half missed
 * heartbeats is the tolerance.
 */
const STALE_AFTER_MS = HEARTBEAT_MS * 2.5;

export function useRowStream(rowId: string | null): RowStream {
  const [status, setStatus] = useState<StreamStatus>('idle');
  const [rev, setRev] = useState(0);
  const [lastPingAt, setLastPingAt] = useState<number | null>(null);

  // Survives reconnects: EventSource retries on its own, and a retry must
  // not look like a fresh subscription that resets everything.
  const hasConnected = useRef(false);
  // Any frame, heartbeat included — this is the liveness clock.
  const lastFrameAt = useRef<number>(0);

  useEffect(() => {
    if (!rowId) {
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

    const source = new EventSource(rowEventsUrl(rowId));

    source.onopen = () => {
      hasConnected.current = true;
      lastFrameAt.current = Date.now();
      setStatus('live');
    };

    source.onmessage = (event) => {
      let ping: RowInvalidation;
      try {
        ping = JSON.parse(event.data);
      } catch {
        // A malformed frame is not worth tearing the stream down for;
        // the next ping supersedes it anyway.
        return;
      }

      hasConnected.current = true;
      lastFrameAt.current = Date.now();
      setStatus('live');

      // A heartbeat proves the backend is alive but nothing changed, so it
      // must not reset the "updated Ns ago" readout — that would make a
      // stalled run look busy.
      if (!ping.heartbeat) setLastPingAt(Date.now());

      // Monotonic guard: a stale frame after a reconnect must not make
      // consumers refetch backwards.
      setRev((current) => (ping.rev > current ? ping.rev : current));
    };

    source.onerror = () => {
      // EventSource reconnects itself; this only reports that it is doing
      // so. Before the first successful open, keep saying `connecting` —
      // "reconnecting" would imply we ever had a connection.
      setStatus(hasConnected.current ? 'reconnecting' : 'connecting');
    };

    // Watchdog for the silent-death case that `onerror` never catches.
    const watchdog = window.setInterval(() => {
      if (Date.now() - lastFrameAt.current > STALE_AFTER_MS) {
        setStatus((current) => (current === 'live' ? 'reconnecting' : current));
      }
    }, HEARTBEAT_MS / 2);

    return () => {
      window.clearInterval(watchdog);
      source.close();
    };
  }, [rowId]);

  return { status, rev, lastPingAt };
}
