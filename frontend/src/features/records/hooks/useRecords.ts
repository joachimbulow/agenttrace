// Record data hooks. Both refetch when `rev` advances — that is the entire
// live-update mechanism. See ADR-0001.

import { useCallback, useEffect, useState } from 'react';
import { getRecord, listRecords } from '@/features/records/api/recordsApi';
import type { RecordListResponse, RecordTreeResponse } from '@/features/records/types/record';

/** Records in a run. `rev` from the open stream so new records appear on their own. */
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
    // First load blocks; later pings swap data underneath (no flash).
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
    // `data` is read only to detect the first load.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [runId, rev]);

  return { data, loading, error };
}

/** Full subtree snapshot for the canvas. Refetched when the record's `rev` advances. */
export function useRecord(recordId: string | null, rev: number) {
  const [data, setData] = useState<RecordTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clear = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  // Clear immediately so the canvas never shows the previous record's cards.
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
