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

// === Records ===
//
// A record is one item of work through the pipeline — the unit the canvas
// renders. It is a projection over spans: `id` IS the record root span's
// id. See docs/decisions/0002-record-as-unit-of-observation.md.

export enum RecordStatus {
  RUNNING = 'running',
  COMPLETED = 'completed',
  ERROR = 'error',
}

export interface RecordSummary {
  id: string;
  run_id: string;
  name: string;
  record_id: string | null;
  policy_id: string | null;
  status: RecordStatus;
  started_at: string;
  ended_at: string | null;
  duration_ms: number | null;
  node_count: number;
}

export interface RecordListResponse {
  run_id: string;
  records: RecordSummary[];
}

export interface RecordTreeResponse {
  id: string;
  run_id: string;
  status: RecordStatus;
  root: TraceNode;
}

/**
 * One invalidation ping. Carries no span data — it means only "this record
 * changed, refetch it". See ADR-0001.
 */
export interface RecordInvalidation {
  record_id: string;
  run_id: string;
  rev: number;
  /** True for a periodic liveness frame carrying no new revision. */
  heartbeat: boolean;
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
