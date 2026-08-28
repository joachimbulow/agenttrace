// API client for backend communication

import type {
  Run,
  RunListResponse,
  RowListResponse,
  RowTreeResponse,
  TraceTreeResponse,
  IngestRequest,
  IngestResponse,
  HealthResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

/**
 * Absolute URL for an endpoint, for consumers that can't go through
 * `fetchApi` — notably `EventSource`, which takes a URL, not a request.
 *
 * Deliberately derived from the same base: docker-compose sets
 * VITE_API_URL to the host without the /api/v1 suffix the default has, so
 * hand-concatenating a stream URL elsewhere would work in dev and break in
 * Docker.
 */
export function apiUrl(endpoint: string): string {
  return `${API_BASE_URL}${endpoint}`;
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
    public data?: unknown
  ) {
    super(message);
    this.name = 'ApiError';
  }
}

async function fetchApi<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;

  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
  });

  if (!response.ok) {
    const errorData = await response.json().catch(() => ({}));
    throw new ApiError(
      response.status,
      `API error: ${response.statusText}`,
      errorData
    );
  }

  return response.json();
}

// === Run API ===

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

// === Row API ===

export async function listRows(runId: string): Promise<RowListResponse> {
  return fetchApi(`/rows?run_id=${encodeURIComponent(runId)}`);
}

export async function getRow(rowId: string): Promise<RowTreeResponse | null> {
  try {
    return await fetchApi<RowTreeResponse>(`/rows/${encodeURIComponent(rowId)}`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
}

/** URL of a row's invalidation stream, for `new EventSource(...)`. */
export function rowEventsUrl(rowId: string): string {
  return apiUrl(`/rows/${encodeURIComponent(rowId)}/events`);
}

// === Ingest API ===

export async function ingestEvents(
  request: IngestRequest
): Promise<IngestResponse> {
  return fetchApi('/ingest/events', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

// === Health API ===

export async function checkHealth(): Promise<HealthResponse> {
  return fetchApi('/health');
}
