// See docs/decisions/0003-layout-per-tick-over-incremental-spawn.md.
import type { TraceNode } from '../../types';

export const CARD_WIDTH = 196;
export const CARD_HEIGHT = 84;

/** Horizontal gap between time slots. */
const SLOT_GAP = 34;
/** Vertical gap between depth bands. */
const BAND_GAP = 58;
/** Vertical gap between concurrent siblings sharing one slot. */
const STACK_GAP = 16;

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
  /** Index within a stack of concurrent siblings sharing this slot. */
  stackIndex: number;
  x: number;
}

/** Overlapping finished intervals. Unfinished spans stay ungrouped — no end would swallow every later sibling. */
function concurrencyGroups(children: TraceNode[]): TraceNode[][] {
  const groups: TraceNode[][] = [];
  let groupEnd = -Infinity;

  for (const child of children) {
    const start = Date.parse(child.started_at);
    const end = child.ended_at ? Date.parse(child.ended_at) : null;
    const last = groups[groups.length - 1];

    if (last && end !== null && start < groupEnd) {
      last.push(child);
      groupEnd = Math.max(groupEnd, end);
    } else {
      groups.push([child]);
      groupEnd = end ?? -Infinity;
    }
  }

  return groups;
}

/** Place the tree from shape, order, and timings. Same tree → same positions. */
export function layoutTree(root: TraceNode): Layout {
  const slots = new Map<string, Slot>();
  const edges: Layout['edges'] = [];
  let nextSlotX = 0;

  const takeSlot = (): number => {
    const x = nextSlotX;
    nextSlotX += CARD_WIDTH + SLOT_GAP;
    return x;
  };

  // Pass 1: depth, slot, stack index.
  const assign = (node: TraceNode, depth: number): number => {
    if (node.children.length === 0) {
      const x = takeSlot();
      slots.set(node.id, { depth, stackIndex: 0, x });
      return x;
    }

    const centres: number[] = [];

    for (const group of concurrencyGroups(node.children)) {
      // Leaves only — a subtree still needs its own horizontal room.
      const stackable = group.length > 1 && group.every((c) => c.children.length === 0);

      if (stackable) {
        const x = takeSlot();
        group.forEach((child, index) => {
          edges.push({ id: `${node.id}->${child.id}`, source: node.id, target: child.id });
          slots.set(child.id, { depth: depth + 1, stackIndex: index, x });
        });
        centres.push(x);
      } else {
        for (const child of group) {
          edges.push({ id: `${node.id}->${child.id}`, source: node.id, target: child.id });
          centres.push(assign(child, depth + 1));
        }
      }
    }

    const x = (centres[0] + centres[centres.length - 1]) / 2;
    slots.set(node.id, { depth, stackIndex: 0, x });
    return x;
  };

  assign(root, 0);

  // Pass 2: band height = deepest stack at that depth.
  const bandStack = new Map<number, number>();
  for (const slot of slots.values()) {
    bandStack.set(slot.depth, Math.max(bandStack.get(slot.depth) ?? 1, slot.stackIndex + 1));
  }

  const bandTop = new Map<number, number>();
  let y = 0;
  for (const depth of [...bandStack.keys()].sort((a, b) => a - b)) {
    bandTop.set(depth, y);
    const rows = bandStack.get(depth) ?? 1;
    y += rows * CARD_HEIGHT + (rows - 1) * STACK_GAP + BAND_GAP;
  }

  const placed: PlacedNode[] = [];
  const collect = (node: TraceNode) => {
    const slot = slots.get(node.id);
    if (slot) {
      placed.push({
        node,
        depth: slot.depth,
        x: slot.x,
        y: (bandTop.get(slot.depth) ?? 0) + slot.stackIndex * (CARD_HEIGHT + STACK_GAP),
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
