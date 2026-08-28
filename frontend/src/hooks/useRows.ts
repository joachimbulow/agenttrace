// Row data hooks. Both refetch when `rev` advances — that is the entire
// live-update mechanism. See ADR-0001.

import { useCallback, useEffect, useState } from 'react';
import { getRow, listRows } from '../api/client';
import type { RowListResponse, RowTreeResponse } from '../types';

/**
 * Rows in a run, refetched whenever the run changes.
 *
 * `rev` comes from the currently-open row stream. Rows that start after
 * the list was first loaded therefore appear on their own.
 */
export function useRows(runId: string | null, rev: number) {
  const [data, setData] = useState<RowListResponse | null>(null);
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

    listRows(runId)
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
 * A row's full subtree, refetched whenever the row's run changes.
 *
 * This is the canvas's data source. The response is a complete snapshot,
 * so the canvas never reconstructs state from deltas.
 */
export function useRow(rowId: string | null, rev: number) {
  const [data, setData] = useState<RowTreeResponse | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<Error | null>(null);

  const clear = useCallback(() => {
    setData(null);
    setError(null);
  }, []);

  // Drop the previous row's tree the moment the selection changes, so the
  // canvas never renders one row's cards under another row's header.
  useEffect(() => {
    clear();
  }, [rowId, clear]);

  useEffect(() => {
    if (!rowId) {
      return;
    }

    let cancelled = false;
    setLoading((current) => current || data === null);

    getRow(rowId)
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
  }, [rowId, rev]);

  return { data, loading, error };
}
