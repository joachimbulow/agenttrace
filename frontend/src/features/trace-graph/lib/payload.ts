// Payload display rules. Pure functions — components only render the results.

import type { SpanEvent } from '@/features/trace-graph/types/trace';

export const PREFERRED_KEYS = [
  'status',
  'confidence',
  'rationale',
  'conflict',
  'reason',
  'branch',
  'known',
] as const;

const MAX_HIGHLIGHTS = 3;
const CARD_SCALAR_CHARS = 42;

export type HighlightKind = 'scalar' | 'chip';

export interface Highlight {
  key: string;
  kind: HighlightKind;
  display: string;
  /** Original scalar/nested value — used by ScalarValue. */
  value?: unknown;
}

export interface DisplayPayload {
  kind: 'output' | 'error';
  value: unknown;
}

export function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === 'object' && value !== null && !Array.isArray(value);
}

export function isScalar(value: unknown): value is string | number | boolean | null {
  return (
    value === null ||
    typeof value === 'string' ||
    typeof value === 'number' ||
    typeof value === 'boolean'
  );
}

export function displayPayload(events: SpanEvent[]): DisplayPayload | null {
  const error = lastOfType(events, 'error');
  if (error) return { kind: 'error', value: unwrapPayload(error.payload) };
  const output = lastOfType(events, 'output');
  if (output) return { kind: 'output', value: unwrapPayload(output.payload) };
  return null;
}

/** Strip `.value` and a single-key object envelope (`{ verdict: { … } }`). */
export function unwrapPayload(payload: unknown): unknown {
  const inner = isRecord(payload) && 'value' in payload ? payload.value : payload;
  if (!isRecord(inner)) return inner;
  const keys = Object.keys(inner);
  if (keys.length === 1 && isRecord(inner[keys[0]])) return inner[keys[0]];
  return inner;
}

export function pickHighlights(value: unknown): Highlight[] {
  if (!isRecord(value)) return scalarOrChip(value);

  const rows: Highlight[] = [];
  const used = new Set<string>();

  for (const key of PREFERRED_KEYS) {
    if (rows.length >= MAX_HIGHLIGHTS) break;
    const found = preferredValue(value, key);
    if (found === undefined) continue;
    rows.push({ key, kind: 'scalar', display: formatScalar(found), value: found });
    used.add(key);
  }

  for (const [key, nested] of Object.entries(value)) {
    if (rows.length >= MAX_HIGHLIGHTS) break;
    if (used.has(key) || !isScalar(nested)) continue;
    rows.push({ key, kind: 'scalar', display: formatScalar(nested), value: nested });
    used.add(key);
  }

  for (const [key, nested] of Object.entries(value)) {
    if (rows.length >= MAX_HIGHLIGHTS) break;
    if (used.has(key) || isScalar(nested)) continue;
    if (!isRecord(nested) && !Array.isArray(nested)) continue;
    rows.push({ key, kind: 'chip', display: chipLabel(key, nested), value: nested });
    used.add(key);
  }

  return rows;
}

export function formatScalar(value: unknown, maxChars = CARD_SCALAR_CHARS): string {
  const text = scalarText(value);
  if (!Number.isFinite(maxChars) || text.length <= maxChars) return text;
  return `${text.slice(0, Math.max(1, maxChars - 1))}…`;
}

function lastOfType(events: SpanEvent[], eventType: string): SpanEvent | undefined {
  for (let i = events.length - 1; i >= 0; i--) {
    if (events[i].event_type === eventType) return events[i];
  }
  return undefined;
}

/** Depth-1 first, then one level into nested plain objects. */
function preferredValue(record: Record<string, unknown>, key: string): unknown {
  if (isScalar(record[key])) return record[key];
  for (const nested of Object.values(record)) {
    if (isRecord(nested) && isScalar(nested[key])) return nested[key];
  }
  return undefined;
}

function scalarOrChip(value: unknown): Highlight[] {
  if (value === undefined) return [];
  if (isScalar(value)) {
    return [{ key: 'value', kind: 'scalar', display: formatScalar(value), value }];
  }
  if (Array.isArray(value)) {
    return [{ key: 'items', kind: 'chip', display: chipLabel('items', value), value }];
  }
  return [];
}

function chipLabel(key: string, value: unknown): string {
  return Array.isArray(value) ? `${value.length} ${key}` : key;
}

function scalarText(value: unknown): string {
  if (value === null) return 'null';
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') {
    if (!Number.isFinite(value)) return String(value);
    if (Number.isInteger(value)) return String(value);
    return String(Math.round(value * 1000) / 1000);
  }
  if (typeof value === 'string') return value.replace(/\s+/g, ' ').trim();
  return String(value);
}
