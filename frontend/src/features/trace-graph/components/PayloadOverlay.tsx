import { NodeToolbar, Position } from '@xyflow/react';
import { PayloadTree } from '@/features/trace-graph/components/PayloadTree';

export function PayloadOverlay({
  value,
  kind = 'output',
}: {
  value: unknown;
  kind?: 'output' | 'error';
}) {
  return (
    <NodeToolbar
      isVisible
      position={Position.Right}
      align="start"
      offset={10}
      className="nodrag nopan nowheel"
    >
      <div
        className="max-h-[min(32rem,70vh)] w-[26rem] overflow-auto rounded-lg border bg-popover p-4 shadow-md"
        role="dialog"
        aria-label={kind === 'error' ? 'Error' : 'Output'}
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <p className="mb-3 font-mono text-[10px] uppercase tracking-wide text-muted-foreground">
          {kind === 'error' ? 'error' : 'output'}
        </p>
        <PayloadTree value={value} />
      </div>
    </NodeToolbar>
  );
}
