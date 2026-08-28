// Trace span domain model - matches backend API schemas

export enum SpanType {
  AGENT_RUN = 'agent_run',
  STEP = 'step',
  TOOL_CALL = 'tool_call',
  LLM_CALL = 'llm_call',
}

export interface SpanEvent {
  id: string;
  event_type: string;
  timestamp: string;
  payload: Record<string, unknown>;
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

export interface TraceTreeResponse {
  run_id: string;
  root: TraceNode | null;
}
