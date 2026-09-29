import type { GraphFilter } from "@/lib/agent/actions";
import type { FGEdge, FGNode, FormulationGraph } from "./types";

export const COLUMN_WIDTH = 250;
export const ROW_HEIGHT = 96;

export interface PositionedNode {
  node: FGNode;
  x: number;
  y: number;
}

const BRANCH_ORDER = ["core", "regulatory", "patent", "abs", "evidence", "action"];

/**
 * Deterministic layered layout: one column per backend `layer`, rows ordered so an
 * ingredient's chain (ingredient → identity → part/resource) stays on the same row.
 */
export function layoutGraph(graph: FormulationGraph, ingredientOrder: string[] = []): PositionedNode[] {
  const rank = new Map(ingredientOrder.map((id, i) => [id, i]));
  const ingredientOf = (n: FGNode) => {
    const m = /^(?:ing|bot|unc|part|bio|action:resolve):(.+)$/.exec(n.id);
    return m ? m[1] : n.ref && rank.has(n.ref) ? n.ref : null;
  };
  const byLayer = new Map<number, FGNode[]>();
  for (const n of graph.nodes) {
    const list = byLayer.get(n.layer) ?? [];
    list.push(n);
    byLayer.set(n.layer, list);
  }
  const layers = [...byLayer.keys()].sort((a, b) => a - b);
  const out: PositionedNode[] = [];
  layers.forEach((layer, col) => {
    const nodes = byLayer.get(layer)!.slice().sort((a, b) => {
      const ia = ingredientOf(a);
      const ib = ingredientOf(b);
      const ra = ia != null ? (rank.get(ia) ?? 999) : 1000;
      const rb = ib != null ? (rank.get(ib) ?? 999) : 1000;
      if (ra !== rb) return ra - rb;
      const ba = BRANCH_ORDER.indexOf(a.branch);
      const bb = BRANCH_ORDER.indexOf(b.branch);
      if (ba !== bb) return ba - bb;
      return a.id.localeCompare(b.id);
    });
    const offset = ((nodes.length - 1) * ROW_HEIGHT) / 2;
    nodes.forEach((node, row) => {
      out.push({ node, x: col * COLUMN_WIDTH, y: row * ROW_HEIGHT - offset });
    });
  });
  return out;
}

/** Node ids visible (not dimmed) under a branch filter. Core nodes always stay visible. */
export function visibleNodeIds(graph: FormulationGraph, filter: GraphFilter): Set<string> {
  if (filter === "all") return new Set(graph.nodes.map((n) => n.id));
  const keep = new Set(graph.nodes.filter((n) => n.branch === "core" || n.branch === filter).map((n) => n.id));
  if (filter === "evidence") {
    for (const e of graph.edges) {
      if (e.type === "supported_by") {
        keep.add(e.source);
        keep.add(e.target);
      }
    }
  }
  return keep;
}

/** Nodes and edges directly connected to `nodeId` (for focus highlighting). */
export function neighbourhood(edges: FGEdge[], nodeId: string): { nodes: Set<string>; edges: Set<string> } {
  const nodes = new Set([nodeId]);
  const ids = new Set<string>();
  for (const e of edges) {
    if (e.source === nodeId || e.target === nodeId) {
      nodes.add(e.source);
      nodes.add(e.target);
      ids.add(e.id);
    }
  }
  return { nodes, edges: ids };
}
