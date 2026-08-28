// Run API

import { ApiError, fetchApi } from '@/shared/api/httpClient';
import type { TraceTreeResponse } from '@/features/trace-graph/types/trace';
import type { Run, RunListResponse } from '@/features/runs/types/run';

export async function listRuns(params: {
  limit?: number;
  offset?: number;
  status?: string;
}): Promise<RunListResponse> {
  const query = new URLSearchParams();
  if (params.limit !== undefined) query.set('limit', String(params.limit));
  if (params.offset !== undefined) query.set('offset', String(params.offset));
  if (params.status) query.set('status', params.status);

  return fetchApi(`/runs?${query.toString()}`);
}

export async function getRun(runId: string): Promise<Run | null> {
  try {
    return await fetchApi<Run>(`/runs/${runId}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

export async function getRunTree(
  runId: string
): Promise<TraceTreeResponse | null> {
  try {
    return await fetchApi<TraceTreeResponse>(`/runs/${runId}/tree`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}
