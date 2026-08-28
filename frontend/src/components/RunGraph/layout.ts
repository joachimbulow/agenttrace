// Tidy-tree layout, recomputed from the full snapshot on every tick.
//
// A trace is a tree, not a DAG — no cycles, one parent per node — so
// dagre's rank assignment and cycle breaking buy nothing here. Forty lines
// of Reingold-Tilford does the job with no dependency.
//
// Laid out LEFT-TO-RIGHT: depth is a column, siblings stack vertically.
// A row of the Primo pipeline is ~3 levels deep and ~7 wide, so top-down
// produces a very wide, very short tree that fitView has to shrink to
// roughly a third scale before it fits a landscape window. Rotating it
// puts the long axis on the screen's long axis and keeps cards readable.
//
// See docs/decisions/0003-layout-per-tick-over-incremental-spawn.md.

import type { TraceNode } from '../../types';

export const CARD_WIDTH = 216;
export const CARD_HEIGHT = 84;

/** Gap between depth columns. */
const COLUMN_GAP = 72;
/** Gap between stacked siblings. */
const ROW_GAP = 22;

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

/**
 * Place every node in a row's subtree.
 *
 * Leaves take sequential vertical slots; a parent centres against its
 * children. Depth maps to a fixed column. The result depends only on the
 * tree's shape and ordering, never on arrival order or previous layouts,
 * so an unchanged subtree lands in exactly the same place on the next tick
 * and does not jitter.
 */
export function layoutTree(root: TraceNode): Layout {
  const placed: PlacedNode[] = [];
  const edges: Layout['edges'] = [];
  let nextLeafSlot = 0;

  const place = (node: TraceNode, depth: number): number => {
    let centre: number;

    if (node.children.length === 0) {
      centre = nextLeafSlot * (CARD_HEIGHT + ROW_GAP);
      nextLeafSlot += 1;
    } else {
      const childCentres = node.children.map((child) => {
        edges.push({ id: `${node.id}->${child.id}`, source: node.id, target: child.id });
        return place(child, depth + 1);
      });
      centre = (childCentres[0] + childCentres[childCentres.length - 1]) / 2;
    }

    placed.push({
      node,
      depth,
      x: depth * (CARD_WIDTH + COLUMN_GAP),
      y: centre,
    });

    return centre;
  };

  place(root, 0);

  const maxX = placed.reduce((max, p) => Math.max(max, p.x), 0);
  const maxY = placed.reduce((max, p) => Math.max(max, p.y), 0);

  return {
    placed,
    edges,
    width: maxX + CARD_WIDTH,
    height: maxY + CARD_HEIGHT,
  };
}

/** Depth-first list of node ids, for spawn diffing against the last tick. */
export function collectIds(root: TraceNode): string[] {
  const ids: string[] = [];
  const walk = (node: TraceNode) => {
    ids.push(node.id);
    node.children.forEach(walk);
  };
  walk(root);
  return ids;
}
