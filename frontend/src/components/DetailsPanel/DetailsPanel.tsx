import { useRunTree } from '../../hooks/useRuns';
import { JsonView } from './JsonView';
import type { TraceNode, SpanEvent } from '../../types';
import './DetailsPanel.css';

export interface DetailsPanelProps {
  runId: string | null;
  selectedNodeId: string | null;
}

export function DetailsPanel({ runId, selectedNodeId }: DetailsPanelProps) {
  const { data } = useRunTree(runId);

  if (!runId || !selectedNodeId || !data) {
    return (
      <div className="details-panel-empty">
        <p>Select a node to view details</p>
      </div>
    );
  }

  // Find the selected node in the tree
  const selectedNode = findNode(data.root, selectedNodeId);

  if (!selectedNode) {
    return (
      <div className="details-panel-empty">
        <p>Node not found</p>
      </div>
    );
  }

  return (
    <div className="details-panel">
      <div className="details-header">
        <h3>{selectedNode.name}</h3>
        <span className={`type-badge type-${selectedNode.span_type}`}>
          {selectedNode.span_type}
        </span>
      </div>

      <div className="details-section">
        <h4>Timing</h4>
        <div className="details-grid">
          <div className="detail-row">
            <span className="label">Started:</span>
            <span className="value">{new Date(selectedNode.started_at).toLocaleString()}</span>
          </div>
          {selectedNode.ended_at && (
            <div className="detail-row">
              <span className="label">Ended:</span>
              <span className="value">{new Date(selectedNode.ended_at).toLocaleString()}</span>
            </div>
          )}
          {selectedNode.duration_ms && (
            <div className="detail-row">
              <span className="label">Duration:</span>
              <span className="value">{(selectedNode.duration_ms / 1000).toFixed(2)}s</span>
            </div>
          )}
        </div>
      </div>

      {selectedNode.events.length > 0 && (
        <div className="details-section">
          <h4>Events</h4>
          <div className="events-list">
            {selectedNode.events.map((event: SpanEvent) => (
              <div key={event.id} className="event-item">
                <div className="event-header">
                  <span className="event-type">{event.event_type}</span>
                  <span className="event-time">
                    {new Date(event.timestamp).toLocaleTimeString()}
                  </span>
                </div>
                {Object.keys(event.payload).length > 0 && (
                  <JsonView data={event.payload} />
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {Object.keys(selectedNode.attributes).length > 0 && (
        <div className="details-section">
          <h4>Attributes</h4>
          <JsonView data={selectedNode.attributes} />
        </div>
      )}
    </div>
  );
}

function findNode(node: TraceNode | null, nodeId: string): TraceNode | null {
  if (!node) return null;
  if (node.id === nodeId) {
    return node;
  }
  for (const child of node.children) {
    const found = findNode(child, nodeId);
    if (found) return found;
  }
  return null;
}