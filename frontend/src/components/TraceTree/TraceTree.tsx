import { useState } from 'react';
import { useRunTree } from '../../hooks/useRuns';
import type { TraceNode } from '../../types';
import './TraceTree.css';

export interface TraceTreeProps {
  runId: string | null;
  onSelectNode: (nodeId: string) => void;
  selectedNodeId: string | null;
}

export function TraceTree({ runId, onSelectNode, selectedNodeId }: TraceTreeProps) {
  const { data, loading, error } = useRunTree(runId);

  if (!runId) {
    return (
      <div className="trace-tree-empty">
        <p>Select a run to view its trace</p>
      </div>
    );
  }

  if (loading) {
    return <div className="trace-tree-loading">Loading trace...</div>;
  }

  if (error) {
    return (
      <div className="trace-tree-error">
        <p>Error: {error.message}</p>
      </div>
    );
  }

  if (!data || !data.root) {
    return (
      <div className="trace-tree-empty">
        <p>No trace data available</p>
      </div>
    );
  }

  return (
    <div className="trace-tree">
      <div className="trace-tree-header">
        <h3>Trace Tree</h3>
      </div>
      <div className="trace-tree-content">
        <TraceNodeComponent
          node={data.root}
          depth={0}
          onSelectNode={onSelectNode}
          selectedNodeId={selectedNodeId}
        />
      </div>
    </div>
  );
}

interface TraceNodeComponentProps {
  node: TraceNode;
  depth: number;
  onSelectNode: (nodeId: string) => void;
  selectedNodeId: string | null;
}

function TraceNodeComponent({ node, depth, onSelectNode, selectedNodeId }: TraceNodeComponentProps) {
  const [isExpanded, setIsExpanded] = useState(true);
  const hasChildren = node.children && node.children.length > 0;

  return (
    <div className="trace-node">
      <div
        className={`trace-node-header ${selectedNodeId === node.id ? 'selected' : ''}`}
        style={{ paddingLeft: `${depth * 16}px` }}
        onClick={() => onSelectNode(node.id)}
      >
        {hasChildren && (
          <button
            className="expand-btn"
            onClick={(e) => {
              e.stopPropagation();
              setIsExpanded(!isExpanded);
            }}
          >
            {isExpanded ? '▼' : '▶'}
          </button>
        )}
        <span className={`node-type-badge type-${node.span_type}`}>
          {node.span_type}
        </span>
        <span className="node-name">{node.name}</span>
        {node.duration_ms && (
          <span className="node-duration">
            {(node.duration_ms / 1000).toFixed(2)}s
          </span>
        )}
      </div>
      {hasChildren && isExpanded && (
        <div className="trace-node-children">
          {node.children.map((child: TraceNode) => (
            <TraceNodeComponent
              key={child.id}
              node={child}
              depth={depth + 1}
              onSelectNode={onSelectNode}
              selectedNodeId={selectedNodeId}
            />
          ))}
        </div>
      )}
    </div>
  );
}