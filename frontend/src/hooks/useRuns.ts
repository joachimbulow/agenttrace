// React hooks for data fetching

import { useState, useEffect, useCallback } from 'react';
import { listRuns } from '../api/client';
import type { RunListResponse } from '../types';

/**
 * How often to re-poll the run list.
 *
 * Runs are the one thing not covered by the invalidation stream: you can
 * only subscribe to a row, and you can't know a row before you know its
 * run. Without this poll, starting the workflow from a terminal would
 * leave the sidebar empty until a manual refresh.
 */
const RUN_LIST_POLL_MS = 2000;

export function useRuns(params: {
  limit?: number;
  offset?: number;
  status?: string;
  pollMs?: number;
} = {}) {
  const { limit, offset, status, pollMs = RUN_LIST_POLL_MS } = params;
  const [data, setData] = useState<RunListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(
    async (options: { quiet?: boolean } = {}) => {
      // Poll refetches must not put the list back into its loading state,
      // or the sidebar flickers every two seconds.
      if (!options.quiet) setLoading(true);
      try {
        const result = await listRuns({ limit, offset, status });
        setData(result);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err : new Error(String(err)));
      } finally {
        if (!options.quiet) setLoading(false);
      }
    },
    [limit, offset, status]
  );

  useEffect(() => {
    fetch();

    if (pollMs <= 0) return;
    const timer = window.setInterval(() => fetch({ quiet: true }), pollMs);
    return () => window.clearInterval(timer);
  }, [fetch, pollMs]);

  return { data, loading, error, refetch: fetch };
}
