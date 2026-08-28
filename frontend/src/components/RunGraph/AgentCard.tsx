// A card on the canvas. Self-coded, not React Flow node chrome — the cards
// are the product; the canvas is a quiet surface behind them.

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { SpanType, type TraceNode } from '../../types';
import { cardStatus, formatDuration, type CardStatus } from './status';
import { CARD_HEIGHT, CARD_WIDTH } from './layout';
import { cn } from '../../lib/utils';

export interface AgentCardData extends Record<string, unknown> {
  node: TraceNode;
  /** True on the first tick this card exists, driving the spawn animation. */
  isNew: boolean;
  selected: boolean;
  onSelect: (nodeId: string) => void;
}

const STATUS_DOT: Record<CardStatus, string> = {
  running: 'bg-[oklch(var(--info))] animate-pulse',
  completed: 'bg-[oklch(var(--success))]',
  error: 'bg-[oklch(var(--destructive))]',
};

const STATUS_RING: Record<CardStatus, string> = {
  running: 'border-[oklch(var(--info)/0.55)]',
  completed: 'border-border',
  error: 'border-[oklch(var(--destructive)/0.6)]',
};

// llm_call and agent_run get their own hues: the two span types worth
// spotting without reading the label.
const TYPE_CHIP: Record<SpanType, string> = {
  [SpanType.AGENT_RUN]: 'bg-[oklch(var(--brand-bg))] text-[oklch(var(--brand-fg))]',
  [SpanType.LLM_CALL]: 'bg-[oklch(var(--llm-bg))] text-[oklch(var(--llm-fg))]',
  [SpanType.TOOL_CALL]: 'bg-[oklch(var(--info-bg))] text-[oklch(var(--info-fg))]',
  [SpanType.STEP]: 'bg-secondary text-secondary-foreground',
};

export function AgentCard({ data }: NodeProps) {
  const { node, isNew, selected, onSelect } = data as AgentCardData;
  const status = cardStatus(node);
  const duration = formatDuration(node.duration_ms);
  const eventCount = node.events.length;

  return (
    <div
      role="button"
      tabIndex={0}
      onClick={() => onSelect(node.id)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          onSelect(node.id);
        }
      }}
      style={{ width: CARD_WIDTH, height: CARD_HEIGHT }}
      className={cn(
        'group flex cursor-pointer flex-col justify-between rounded-lg border bg-card p-3 text-left',
        'shadow-sm transition-[box-shadow,border-color,transform] duration-200',
        'hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
        STATUS_RING[status],
        selected && 'ring-2 ring-ring',
        isNew && 'agenttrace-spawn'
      )}
    >
      <Handle type="target" position={Position.Left} className="!opacity-0" />

      <div className="flex items-start gap-2">
        <span
          aria-hidden
          className={cn('mt-1.5 h-2 w-2 shrink-0 rounded-full', STATUS_DOT[status])}
        />
        <span
          className="truncate text-sm font-medium leading-snug text-card-foreground"
          title={node.name}
        >
          {node.name}
        </span>
      </div>

      <div className="flex items-center justify-between gap-2">
        <span
          className={cn(
            'rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-wide',
            TYPE_CHIP[node.span_type] ?? TYPE_CHIP[SpanType.STEP]
          )}
        >
          {node.span_type}
        </span>
        <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
          {duration ?? (status === 'running' ? 'running…' : '—')}
          {eventCount > 0 && <span className="ml-2 opacity-70">{eventCount}e</span>}
        </span>
      </div>

      <Handle type="source" position={Position.Right} className="!opacity-0" />
    </div>
  );
}
