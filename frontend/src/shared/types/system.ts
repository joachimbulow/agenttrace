// System-level API types shared across features

export interface IngestEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface IngestRequest {
  run_id: string;
  run_name?: string;
  events: IngestEvent[];
}

export interface IngestResponse {
  accepted: number;
  run_id: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}
