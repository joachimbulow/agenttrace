import { NodeToolbar, Position } from '@xyflow/react';
import { PayloadTree } from '@/features/trace-graph/components/PayloadTree';

export function PayloadOverlay({ value }: { value: unknown }) {
  return (
    <NodeToolbar
      isVisible
      position={Position.Right}
      align="start"
      offset={10}
      className="nodrag nopan nowheel"
    >
      <div
        className="max-h-80 w-72 overflow-auto rounded-lg border bg-popover p-3 shadow-md"
        role="dialog"
        aria-label="Payload"
        onMouseDown={(event) => event.stopPropagation()}
        onClick={(event) => event.stopPropagation()}
      >
        <PayloadTree value={value} />
      </div>
    </NodeToolbar>
  );
}
