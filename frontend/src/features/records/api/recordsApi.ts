// Record API

import { apiUrl, ApiError, fetchApi } from '@/shared/api/httpClient';
import type { RecordListResponse, RecordTreeResponse } from '@/features/records/types/record';

export async function listRecords(runId: string): Promise<RecordListResponse> {
  return fetchApi(`/records?run_id=${encodeURIComponent(runId)}`);
}

export async function getRecord(recordId: string): Promise<RecordTreeResponse | null> {
  try {
    return await fetchApi<RecordTreeResponse>(`/records/${encodeURIComponent(recordId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/** URL of a record's invalidation stream, for `new EventSource(...)`. */
export function recordEventsUrl(recordId: string): string {
  return apiUrl(`/records/${encodeURIComponent(recordId)}/events`);
}
