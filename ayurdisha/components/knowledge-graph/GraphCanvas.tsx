"use client";

import { useEffect, useMemo, useRef, useState, useSyncExternalStore } from "react";
import ForceGraph2D, {
  type ForceGraphMethods,
  type LinkObject,
  type NodeObject,
} from "react-force-graph-2d";
import type { KgGraph, KgNode } from "@/lib/types";
import { labelColor, labelIcon } from "./labels";

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

function truncate(text: string, max = 22) {
  return text.length > max ? `${text.slice(0, max - 1)}…` : text;
}

/** Hex‑to‑rgba: append alpha to a #rrggbb string. */
function hexAlpha(hex: string, alpha: number) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r},${g},${b},${alpha})`;
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
  const [hoverNode, setHoverNode] = useState<string | null>(null);

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
    fg.d3Force("charge")?.strength?.(-360);
    fg.d3Force("link")?.distance?.(120);
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
          warmupTicks={80}
          cooldownTicks={120}

          /* ── Links ─────────────────────────────────────── */
          linkCurvature={0.12}
          linkColor={() => dark ? "rgba(140,160,145,0.18)" : "rgba(100,120,105,0.15)"}
          linkWidth={1}
          linkDirectionalArrowLength={3.5}
          linkDirectionalArrowRelPos={1}
          linkDirectionalArrowColor={() => dark ? "rgba(140,160,145,0.4)" : "rgba(100,120,105,0.35)"}
          linkDirectionalParticles={2}
          linkDirectionalParticleWidth={1.4}
          linkDirectionalParticleSpeed={0.005}
          linkDirectionalParticleColor={(link) => hexAlpha(labelColor(((link as GLink).source as GNode).node.label), 0.5)}
          linkLabel={(l) => l.type.replaceAll("_", " ").toLowerCase()}

          onEngineStop={() => {
            if (!fitted.current) {
              fitted.current = true;
              fgRef.current?.zoomToFit(400, 60);
            }
          }}
          onNodeClick={(n) => onSelect(n.node)}
          onBackgroundClick={() => onSelect(null)}
          onNodeHover={(n) => setHoverNode(n ? n.id : null)}
          nodeLabel={(n) => `${n.node.label}: ${n.node.name}`}

          /* ── Nodes ─────────────────────────────────────── */
          nodeCanvasObjectMode={() => "replace"}
          nodeCanvasObject={(n, ctx, scale) => {
            const selected = n.id === selectedKey;
            const hovered = n.id === hoverNode;
            const color = labelColor(n.node.label);
            const cx = n.x ?? 0;
            const cy = n.y ?? 0;

            /* ── Radius ── */
            const r = n.center ? 14 : 7;

            /* ── Subtle ambient shadow (no neon glow) ── */
            ctx.shadowColor = dark ? "rgba(0,0,0,0.5)" : "rgba(20,38,28,0.18)";
            ctx.shadowBlur = hovered ? 8 : 4;
            ctx.shadowOffsetY = 1;

            /* ── Fill: solid matte colour ── */
            ctx.beginPath();
            ctx.arc(cx, cy, r, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();

            /* ── Border ring ── */
            ctx.shadowBlur = 0;
            ctx.shadowOffsetY = 0;
            ctx.lineWidth = (n.center ? 2.5 : 1.5) / scale;
            ctx.strokeStyle = dark ? "rgba(255,255,255,0.25)" : "rgba(255,255,255,0.7)";
            ctx.stroke();

            /* ── Center node: second outer ring ── */
            if (n.center) {
              ctx.beginPath();
              ctx.arc(cx, cy, r + 3.5 / scale, 0, 2 * Math.PI);
              ctx.lineWidth = 1.2 / scale;
              ctx.strokeStyle = hexAlpha(color, 0.45);
              ctx.stroke();
            }

            /* ── Selection indicator: clean solid ring ── */
            if (selected) {
              ctx.beginPath();
              ctx.arc(cx, cy, r + (n.center ? 6 : 4.5) / scale, 0, 2 * Math.PI);
              ctx.lineWidth = 1.6 / scale;
              ctx.strokeStyle = dark ? "#e5e5e5" : "#14261c";
              ctx.stroke();
            }

            /* ── Icon inside node ── */
            const icon = labelIcon(n.node.label);
            const iconSize = n.center ? 10 : 6;
            ctx.font = `${iconSize}px sans-serif`;
            ctx.textAlign = "center";
            ctx.textBaseline = "middle";
            ctx.fillStyle = "rgba(255,255,255,0.9)";
            ctx.fillText(icon, cx, cy + 0.5);

            /* ── Text label ── */
            if (n.center || selected || hovered || scale > 1.5) {
              const fontSize = Math.max(11 / scale, 2.8);
              ctx.font = `${n.center || selected ? "600 " : ""}${fontSize}px Inter, system-ui, sans-serif`;
              const label = truncate(n.node.name);

              const tm = ctx.measureText(label);
              const tw = tm.width;
              const px = 3.5 / scale;
              const py = 1.5 / scale;
              const labelY = cy + r + 5 / scale;

              /* Pill bg */
              ctx.beginPath();
              const pillX = cx - tw / 2 - px;
              const pillY = labelY - py;
              const pillW = tw + px * 2;
              const pillH = fontSize + py * 2;
              if (ctx.roundRect) ctx.roundRect(pillX, pillY, pillW, pillH, 3 / scale);
              else ctx.rect(pillX, pillY, pillW, pillH);
              ctx.fillStyle = dark ? "rgba(15,23,20,0.8)" : "rgba(255,255,255,0.92)";
              ctx.fill();

              /* Text */
              ctx.textAlign = "center";
              ctx.textBaseline = "top";
              ctx.fillStyle = dark ? "#c8d0ca" : "#2c3e33";
              ctx.fillText(label, cx, labelY);
            }
          }}
          nodePointerAreaPaint={(n, color, ctx) => {
            ctx.beginPath();
            ctx.arc(n.x ?? 0, n.y ?? 0, n.center ? 18 : 11, 0, 2 * Math.PI);
            ctx.fillStyle = color;
            ctx.fill();
          }}
        />
      )}
    </div>
  );
}
