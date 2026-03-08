// API client for backend communication

import type {
  Run,
  RunListResponse,
  TraceTreeResponse,
  IngestRequest,
  IngestResponse,
  HealthResponse,
} from '../types';

const API_BASE_URL = import.meta.env.VITE_API_URL || 'http://localhost:8000/api/v1';

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
    return fetchApi<Run>(`/runs/${runId}`);
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
    return fetchApi<TraceTreeResponse>(`/runs/${runId}/tree`);
  } catch (error) {
    if (error instanceof ApiError && error.status === 404) {
      return null;
    }
    throw error;
  }
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
