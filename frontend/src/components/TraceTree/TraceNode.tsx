import type { TraceNode as TraceNodeType } from '../../types';

export interface TraceNodeProps {
  node: TraceNodeType;
  depth: number;
  isExpanded: boolean;
  onToggleExpand: () => void;
  onSelect: () => void;
  isSelected: boolean;
}

export function TraceNode({
  node,
  depth,
  isExpanded,
  onToggleExpand,
  onSelect,
  isSelected,
}: TraceNodeProps) {
  const hasChildren = node.children.length > 0;

  return (
    <div className="trace-node" style={{ marginLeft: depth * 16 }}>
      <div className={`trace-node-content ${isSelected ? 'selected' : ''}`} onClick={onSelect}>
        {hasChildren && (
          <button className="expand-button" onClick={(e) => { e.stopPropagation(); onToggleExpand(); }}>
            {isExpanded ? '▼' : '▶'}
          </button>
        )}
        <span className={`type-badge type-${node.span_type}`}>
          {node.span_type}
        </span>
        <span className="node-name">{node.name}</span>
        {node.duration_ms && (
          <span className="duration">{(node.duration_ms / 1000).toFixed(2)}s</span>
        )}
      </div>
    </div>
  );
}