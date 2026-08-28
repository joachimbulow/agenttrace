// A card on the canvas. Self-coded, not React Flow node chrome — the cards
// are the product; the canvas is a quiet surface behind them.

import { Handle, Position, type NodeProps } from '@xyflow/react';
import { Bot, ChevronRight, Sparkles, Wrench, type LucideIcon } from 'lucide-react';
import { SpanType, type TraceNode } from '@/features/trace-graph/types/trace';
import { cardStatus, formatDuration, type CardStatus } from '@/features/trace-graph/lib/status';
import { CARD_HEIGHT, CARD_WIDTH } from '@/features/trace-graph/lib/layout';
import { displayPayload, pickHighlights } from '@/features/trace-graph/lib/payload';
import { PayloadHighlights } from '@/features/trace-graph/components/PayloadHighlights';
import { PayloadOverlay } from '@/features/trace-graph/components/PayloadOverlay';
import { cn } from '@/shared/lib/utils';

export interface AgentCardData extends Record<string, unknown> {
  node: TraceNode;
  /** First tick this card exists — drives spawn. */
  isNew: boolean;
  selected: boolean;
  onSelect: (nodeId: string | null) => void;
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

interface TypeStyle {
  label: string;
  icon: LucideIcon;
  chip: string;
  /** Left-edge accent when the chip is too small to read. */
  spine: string;
}

const TYPE_STYLE: Record<SpanType, TypeStyle> = {
  [SpanType.AGENT_RUN]: {
    label: 'agent',
    icon: Bot,
    chip: 'bg-[oklch(var(--brand-bg))] text-[oklch(var(--brand-fg))]',
    spine: 'bg-[oklch(var(--primary))]',
  },
  [SpanType.LLM_CALL]: {
    label: 'llm',
    icon: Sparkles,
    chip: 'bg-[oklch(var(--llm-bg))] text-[oklch(var(--llm-fg))]',
    spine: 'bg-[oklch(var(--llm-fg))]',
  },
  [SpanType.TOOL_CALL]: {
    label: 'tool',
    icon: Wrench,
    chip: 'bg-[oklch(var(--info-bg))] text-[oklch(var(--info-fg))]',
    spine: 'bg-[oklch(var(--info))]',
  },
  [SpanType.STEP]: {
    label: 'step',
    icon: ChevronRight,
    chip: 'bg-secondary text-secondary-foreground',
    spine: 'bg-border',
  },
};

export function AgentCard({ data }: NodeProps) {
  const { node, isNew, selected, onSelect } = data as AgentCardData;
  const status = cardStatus(node);
  const duration = formatDuration(node.duration_ms);
  const payload = displayPayload(node.events);
  const highlights = payload ? pickHighlights(payload.value) : [];
  const type = TYPE_STYLE[node.span_type] ?? TYPE_STYLE[SpanType.STEP];
  const TypeIcon = type.icon;

  return (
    <div style={{ width: CARD_WIDTH, height: CARD_HEIGHT }} className="relative nopan">
      <div
        role="button"
        tabIndex={0}
        onKeyDown={(e) => {
          if (e.key === 'Enter' || e.key === ' ') {
            e.preventDefault();
            onSelect(selected ? null : node.id);
          }
        }}
        className={cn(
          'flex h-full cursor-pointer flex-col justify-between overflow-hidden',
          'relative rounded-lg border bg-card py-2.5 pl-4 pr-3 text-left',
          'shadow-sm transition-[box-shadow,border-color,transform] duration-200',
          'hover:shadow-md focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring',
          STATUS_RING[status],
          selected && 'ring-2 ring-ring',
          isNew && 'agenttrace-spawn'
        )}
      >
        <span aria-hidden className={cn('absolute inset-y-0 left-0 w-1', type.spine)} />

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

        <PayloadHighlights rows={highlights} />

        <div className="flex items-center justify-between gap-2">
          <span
            className={cn(
              'inline-flex items-center gap-1 rounded px-1.5 py-0.5 font-mono',
              'text-[10px] uppercase tracking-wide',
              type.chip
            )}
          >
            <TypeIcon aria-hidden className="h-3 w-3" strokeWidth={2.5} />
            {type.label}
          </span>
          <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
            {duration ?? (status === 'running' ? 'running…' : '—')}
          </span>
        </div>
      </div>

      {/* Flow is top-down, so edges enter the top and leave the bottom. */}
      <Handle type="target" position={Position.Top} className="!opacity-0" />
      {selected && payload && <PayloadOverlay value={payload.value} />}
      <Handle type="source" position={Position.Bottom} className="!opacity-0" />
    </div>
  );
}
