// See docs/decisions/0003-layout-per-tick-over-incremental-spawn.md.
import type { TraceNode } from '@/features/trace-graph/types/trace';

export const CARD_WIDTH = 196;
export const CARD_HEIGHT = 132;

/** Horizontal gap between leaf columns. */
const SLOT_GAP = 34;
/** Vertical gap between depth bands. */
const BAND_GAP = 58;

export interface PlacedNode {
  node: TraceNode;
  depth: number;
  x: number;
  y: number;
}

export interface Layout {
  placed: PlacedNode[];
  edges: Array<{ id: string; source: string; target: string }>;
  width: number;
  height: number;
}

interface Slot {
  depth: number;
  x: number;
}

/** Tidy-tree: depth → y, siblings fan out on x, parents centre over children. */
export function layoutTree(root: TraceNode): Layout {
  const slots = new Map<string, Slot>();
  const edges: Layout['edges'] = [];
  let nextSlotX = 0;

  const takeSlot = (): number => {
    const x = nextSlotX;
    nextSlotX += CARD_WIDTH + SLOT_GAP;
    return x;
  };

  const assign = (node: TraceNode, depth: number): number => {
    if (node.children.length === 0) {
      const x = takeSlot();
      slots.set(node.id, { depth, x });
      return x;
    }

    const centres: number[] = [];
    for (const child of node.children) {
      edges.push({ id: `${node.id}->${child.id}`, source: node.id, target: child.id });
      centres.push(assign(child, depth + 1));
    }

    const x = (centres[0] + centres[centres.length - 1]) / 2;
    slots.set(node.id, { depth, x });
    return x;
  };

  assign(root, 0);

  const placed: PlacedNode[] = [];
  const collect = (node: TraceNode) => {
    const slot = slots.get(node.id);
    if (slot) {
      placed.push({
        node,
        depth: slot.depth,
        x: slot.x,
        y: slot.depth * (CARD_HEIGHT + BAND_GAP),
      });
    }
    node.children.forEach(collect);
  };
  collect(root);

  const maxX = placed.reduce((max, p) => Math.max(max, p.x), 0);
  const maxY = placed.reduce((max, p) => Math.max(max, p.y), 0);

  return { placed, edges, width: maxX + CARD_WIDTH, height: maxY + CARD_HEIGHT };
}

/** DFS node ids, for spawn diffing. */
export function collectIds(root: TraceNode): string[] {
  const ids: string[] = [];
  const walk = (node: TraceNode) => {
    ids.push(node.id);
    node.children.forEach(walk);
  };
  walk(root);
  return ids;
}
