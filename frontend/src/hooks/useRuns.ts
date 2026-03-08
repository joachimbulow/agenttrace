// React hooks for data fetching

import { useState, useEffect, useCallback } from 'react';
import { listRuns, getRun, getRunTree } from '../api/client';
import type { Run, RunListResponse, TraceTreeResponse } from '../types';

export function useRuns(params: {
  limit?: number;
  offset?: number;
  status?: string;
} = {}) {
  const [data, setData] = useState<RunListResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const fetch = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await listRuns(params);
      setData(result);
    } catch (err) {
      setError(err instanceof Error ? err : new Error(String(err)));
    } finally {
      setLoading(false);
    }
  }, [params.limit, params.offset, params.status]);

  useEffect(() => {
    fetch();
  }, [fetch]);

  return { data, loading, error, refetch: fetch };
}

export function useRun(runId: string | null) {
  const [data, setData] = useState<Run | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    getRun(runId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err : new Error(String(err))))
      .finally(() => setLoading(false));
  }, [runId]);

  return { data, loading, error };
}

export function useRunTree(runId: string | null) {
  const [data, setData] = useState<TraceTreeResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(null);
      setLoading(false);
      return;
    }

    setLoading(true);
    setError(null);

    getRunTree(runId)
      .then(setData)
      .catch((err) => setError(err instanceof Error ? err : new Error(String(err))))
      .finally(() => setLoading(false));
  }, [runId]);

  return { data, loading, error };
}
