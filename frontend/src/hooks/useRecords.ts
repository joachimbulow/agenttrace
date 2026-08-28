// Record data hooks. Both refetch when `rev` advances — that is the entire
// live-update mechanism. See ADR-0001.

import { useCallback, useEffect, useState } from 'react';
import { getRecord, listRecords } from '../api/client';
import type { RecordListResponse, RecordTreeResponse } from '../types';

/**
 * Records in a run, refetched whenever the run changes.
 *
 * `rev` comes from the currently-open record stream. Records that start
 * after the list was first loaded therefore appear on their own.
 */
export function useRecords(runId: string | null, rev: number) {
  const [data, setData] = useState<RecordListResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  useEffect(() => {
    if (!runId) {
      setData(null);
      setError(null);
      return;
    }

    let cancelled = false;
    // Only the first load blocks the UI; later refetches swap data
    // underneath so the list doesn't flash on every ping.
    setLoading((current) => current || data === null);

    listRecords(runId)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // `data` is deliberately not a dependency — it is read only to decide
    // whether this is the first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, rev]);

  return { data, loading, error };
}

/**
 * A record's full subtree, refetched whenever the record's run changes.
 *
 * This is the canvas's data source. The response is a complete snapshot,
 * so the canvas never reconstructs state from deltas.
 */
export function useRecord(recordId: string | null, rev: number) {
  const [data, setData] = useState<RecordTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clear = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  // Drop the previous record's tree the moment the selection changes, so
  // the canvas never renders one record's cards under another record's header.
  useEffect(() => {
    clear();
  }, [recordId, clear]);

  useEffect(() => {
    if (!recordId) {
      return;
    }

    let cancelled = false;
    setLoading((current) => current || data === null);

    getRecord(recordId)
      .then((result) => {
        if (!cancelled) {
          setData(result);
          setError(null);
        }
      })
      .catch((err) => {
        if (!cancelled) setError(err instanceof Error ? err : new Error(String(err)));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [recordId, rev]);

  return { data, loading, error };
}
