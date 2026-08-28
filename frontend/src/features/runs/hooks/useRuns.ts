// React hooks for run data fetching

import { useState, useEffect, useCallback } from 'react';
import { listRuns } from '@/features/runs/api/runsApi';
import type { RunListResponse } from '@/features/runs/types/run';

/** Poll interval. Runs aren't on the invalidation stream — you need a run before you can subscribe to a record. */
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
      // Poll must not flash the list back into loading.
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
