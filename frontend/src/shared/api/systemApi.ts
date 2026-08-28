// System-level API endpoints (ingest, health)

import { fetchApi } from '@/shared/api/httpClient';
import type { HealthResponse, IngestRequest, IngestResponse } from '@/shared/types/system';

export async function ingestEvents(
  request: IngestRequest
): Promise<IngestResponse> {
  return fetchApi('/ingest/events', {
    method: 'POST',
    body: JSON.stringify(request),
  });
}

export async function checkHealth(): Promise<HealthResponse> {
  return fetchApi('/health');
}
