"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import ForceGraph2D, {
  type ForceGraphMethods,
  type LinkObject,
  type NodeObject,
} from "react-force-graph-2d";
import type { KgGraph, KgNode } from "@/lib/types";
import { labelColor } from "./labels";

type GNode = NodeObject<{ id: string; node: KgNode; center: boolean }>;
type GLink = LinkObject<GNode, { type: string }>;

function useSize<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [size, setSize] = useState({ width: 0, height: 0 });
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const obs = new ResizeObserver(([entry]) => {
      const { width, height } = entry.contentRect;
      setSize({ width: Math.floor(width), height: Math.floor(height) });
    });
    obs.observe(el);
    return () => obs.disconnect();
  }, []);
  return [ref, size] as const;
}

const DARK_QUERY = "(prefers-color-scheme: dark)";

function subscribeDarkMode(onChange: () => void) {
  const mq = window.matchMedia(DARK_QUERY);
  mq.addEventListener("change", onChange);
  return () => mq.removeEventListener("change", onChange);
}

function useDarkMode() {
  return useSyncExternalStore(
    subscribeDarkMode,
    () => window.matchMedia(DARK_QUERY).matches,
    () => false,
  );
}

function truncate(text: string, max = 24) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

export default function GraphCanvas({
  graph,
  selectedKey,
  onSelect,
}: {
  graph: KgGraph;
  selectedKey: string | null;
  onSelect: (node: KgNode | null) => void;
}) {
  const [containerRef, { width, height }] = useSize<HTMLDivElement>();
  const fgRef = useRef<ForceGraphMethods<GNode, GLink>>(undefined);
  const fitted = useRef(false);
  const dark = useDarkMode();

  const data = useMemo(
    () => ({
      nodes: graph.nodes.map<GNode>((n) => ({
        id: n.key,
        node: n,
        center: n.key === graph.center,
      })),
      links: graph.edges.map<GLink>((e) => ({
        source: e.source,
        target: e.target,
        type: e.type,
      })),
    }),
    [graph],
  );

  const ready = width > 0 && height > 0;

  useEffect(() => {
    const fg = fgRef.current;
    if (!fg) return;
    fitted.current = false;
    fg.d3Force("charge")?.strength?.(-320);
    fg.d3Force("link")?.distance?.(110);
    fg.d3ReheatSimulation();
  }, [data, ready]);

  return (
    <div ref={containerRef} className="h-full w-full">
      {ready && (
        <ForceGraph2D<GNode, GLink>
          ref={fgRef}
          graphData={data}
          width={width}
          height={height}
          nodeId="id"
          nodeRelSize={5}
          nodeVal={(n) => (n.center ? 4 : 1.4)}
          nodeLabel={(n) => `${n.node.label}: ${n.node.name}`}
          linkLabel={(l) => l.type.replaceAll("_", " ").toLowerCase()}
          linkColor={() => (dark ? "rgba(163,163,163,0.35)" : "rgba(115,115,115,0.35)")}
          linkDirectionalArrowLength={3}
          linkDirectionalArrowRelPos={1}
          cooldownTicks={120}
          onEngineStop={() => {
            if (!fitted.current) {
              fitted.current = true;
              fgRef.current?.zoomToFit(400, 60);
            }
          }}
          onNodeClick={(n) => onSelect(n.node)}
          onBackgroundClick={() => onSelect(null)}
          nodeCanvasObjectMode={() => "replace"}
          nodeCanvasObject={(n, ctx, scale) => {
            const r = n.center ? 10 : 6;
            const selected = n.id === selectedKey;
            ctx.beginPath();
            ctx.arc(n.x ?? 0, n.y ?? 0, r, 0, 2 * Math.PI);
            ctx.fillStyle = labelColor(n.node.label);
            ctx.fill();
            if (selected || n.center) {
              ctx.lineWidth = 2.5 / scale;
              ctx.strokeStyle = dark ? "#fafafa" : "#171717";
              ctx.stroke();
            }
            if (n.center || selected || scale > 1.4) {
              const fontSize = Math.max(11 / scale, 2.5);
              ctx.font = `${n.center ? "600 " : ""}${fontSize}px sans-serif`;
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = dark ? "#e5e5e5" : "#262626";
              ctx.fillText(truncate(n.node.name), n.x ?? 0, (n.y ?? 0) + r + 2);
            }
          }}
          nodePointerAreaPaint={(n, color, ctx) => {
            ctx.beginPath();
            ctx.arc(n.x ?? 0, n.y ?? 0, n.center ? 12 : 8, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
