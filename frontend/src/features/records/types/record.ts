// Record domain model - matches backend API schemas.
// One pipeline item — the canvas unit. `id` is the root span's id. ADR-0002.

import type { TraceNode } from '@/features/trace-graph/types/trace';

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

/** Invalidation ping: no span data, just "refetch this record". ADR-0001. */
export interface RecordInvalidation {
  record_id: string;
  run_id: string;
  rev: number;
  /** True for a periodic liveness frame carrying no new revision. */
  heartbeat: boolean;
}
