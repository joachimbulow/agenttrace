// Type definitions for Agent Trace - matches backend API schemas

// === Enums ===

export enum SpanType {
  AGENT_RUN = 'agent_run',
  STEP = 'step',
  TOOL_CALL = 'tool_call',
  LLM_CALL = 'llm_call',
}

export enum RunStatus {
  RUNNING = 'running',
  COMPLETED = 'completed',
  FAILED = 'failed',
}

// === API Types ===

export interface Run {
  id: string;
  name: string;
  status: RunStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  metadata: Record<string, unknown>;
  node_count: number | null;
  created_at: string;
  updated_at: string;
}

export interface RunListResponse {
  runs: Run[];
  total: number;
  limit: number;
  offset: number;
}

export interface TraceNode {
  id: string;
  name: string;
  span_type: SpanType;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  attributes: Record<string, unknown>;
  children: TraceNode[];
  events: SpanEvent[];
}

export interface SpanEvent {
  id: string;
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
}

export interface TraceTreeResponse {
  run_id: string;
  root: TraceNode | null;
}

export interface IngestRequest {
  run_id: string;
  run_name?: string;
  events: IngestEvent[];
}

export interface IngestEvent {
  type: string;
  data: Record<string, unknown>;
}

export interface IngestResponse {
  accepted: number;
  run_id: string;
}

export interface HealthResponse {
  status: string;
  version: string;
}
