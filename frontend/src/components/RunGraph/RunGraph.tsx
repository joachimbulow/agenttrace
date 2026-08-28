// The live canvas. React Flow is used as a dumb viewport only — pan and
// zoom, custom node types, no background grid, no controls, no minimap.

import { useEffect, useMemo, useRef } from 'react';
import {
  Background,
  BackgroundVariant,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
  type Edge,
  type Node,
} from '@xyflow/react';
import '@xyflow/react/dist/style.css';

import type { RowSummary, TraceNode } from '../../types';
import { AgentCard, type AgentCardData } from './AgentCard';
import { CARD_HEIGHT, CARD_WIDTH, collectIds, layoutTree } from './layout';
import './RunGraph.css';

const NODE_TYPES = { agentCard: AgentCard };

interface RunGraphProps {
  root: TraceNode | null;
  row: RowSummary | null;
  selectedNodeId: string | null;
  onSelectNode: (nodeId: string) => void;
  loading: boolean;
}

function Canvas({ root, selectedNodeId, onSelectNode }: Omit<RunGraphProps, 'loading' | 'row'>) {
  const { fitView } = useReactFlow();

  // Ids we have already rendered. A card is animated in only on the tick
  // it first appears — this is how spawn is detected now that the client
  // receives whole snapshots rather than span_start events (ADR-0003).
  const seenIds = useRef<Set<string>>(new Set());
  const nodeCount = root ? collectIds(root).length : 0;

  const { nodes, edges } = useMemo(() => {
    if (!root) return { nodes: [] as Node[], edges: [] as Edge[] };

    const layout = layoutTree(root);
    const previouslySeen = seenIds.current;

    const flowNodes: Node[] = layout.placed.map(({ node, x, y }) => ({
      id: node.id,
      type: 'agentCard',
      position: { x, y },
      // React Flow needs the size up front to route edges; the card itself
      // is fixed-size for now (fluid resize is deferred).
      width: CARD_WIDTH,
      height: CARD_HEIGHT,
      data: {
        node,
        isNew: !previouslySeen.has(node.id),
        selected: node.id === selectedNodeId,
        onSelect: onSelectNode,
      } satisfies AgentCardData,
    }));

    const flowEdges: Edge[] = layout.edges.map((edge) => ({
      ...edge,
      type: 'smoothstep',
      animated: false,
      style: { strokeWidth: 1.5 },
      className: 'agenttrace-edge',
    }));

    return { nodes: flowNodes, edges: flowEdges };
  }, [root, selectedNodeId, onSelectNode]);

  // Recorded after render so the current tick still sees them as new.
  useEffect(() => {
    if (root) seenIds.current = new Set(collectIds(root));
  }, [root]);

  // Keep the whole row in frame as it grows, but only when the shape
  // actually changed — refitting on every ping would fight the user's pan.
  useEffect(() => {
    if (nodeCount === 0) return;
    const timer = window.setTimeout(() => {
      fitView({ padding: 0.2, duration: 320, maxZoom: 1 });
    }, 60);
    return () => window.clearTimeout(timer);
  }, [nodeCount, fitView]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={NODE_TYPES}
      proOptions={{ hideAttribution: true }}
      nodesDraggable={false}
      nodesConnectable={false}
      elementsSelectable={false}
      minZoom={0.2}
      maxZoom={1.6}
      className="agenttrace-canvas"
    >
      {/* A whisper of texture so pan reads as movement, not a static image. */}
      <Background variant={BackgroundVariant.Dots} gap={28} size={1} className="agenttrace-bg" />
    </ReactFlow>
  );
}

export function RunGraph({ root, row, selectedNodeId, onSelectNode, loading }: RunGraphProps) {
  if (!row) {
    return <EmptyState title="No row selected" hint="Pick a run, then a row, to watch it run." />;
  }

  if (!root) {
    return loading ? (
      <EmptyState title="Loading row…" hint={null} />
    ) : (
      // A started row whose spans haven't landed yet is a valid live state,
      // distinct from "nothing selected".
      <EmptyState title="Waiting for the first span" hint={row.name} />
    );
  }

  return (
    <div className="h-full w-full">
      <ReactFlowProvider>
        <Canvas root={root} selectedNodeId={selectedNodeId} onSelectNode={onSelectNode} />
      </ReactFlowProvider>
    </div>
  );
}

function EmptyState({ title, hint }: { title: string; hint: string | null }) {
  return (
    <div className="flex h-full flex-col items-center justify-center gap-1.5 px-6 text-center">
      <p className="text-sm font-medium text-foreground">{title}</p>
      {hint && <p className="font-mono text-xs text-muted-foreground">{hint}</p>}
    </div>
  );
}
