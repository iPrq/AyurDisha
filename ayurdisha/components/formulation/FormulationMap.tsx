"use client";

import "@xyflow/react/dist/base.css";
import {
  Background,
  BackgroundVariant,
  Controls,
  Handle,
  MarkerType,
  type Edge,
  type Node,
  type NodeProps,
  Position,
  ReactFlow,
  ReactFlowProvider,
  useReactFlow,
} from "@xyflow/react";
import { memo, useEffect, useMemo } from "react";
import type { GraphFilter } from "@/lib/agent/actions";
import { layoutGraph, neighbourhood, visibleNodeIds } from "@/lib/formulation/layout";
import type { FGNode, FormulationGraph, GraphBranch, IdentityStatus } from "@/lib/formulation/types";

type CardData = { fg: FGNode; dimmed: boolean; focused: boolean; selected: boolean };
type CardNode = Node<CardData, "fg">;

const BRANCH_ACCENT: Record<GraphBranch, string> = {
  core: "border-l-green-700",
  regulatory: "border-l-sky-600",
  patent: "border-l-violet-600",
  abs: "border-l-orange-600",
  evidence: "border-l-teal-600",
  action: "border-l-green-800",
};

const TYPE_LABEL: Record<string, string> = {
  formulation: "Formulation",
  composition: "Composition",
  ingredient: "Ingredient",
  botanical_identity: "Botanical identity",
  plant_part: "Plant part",
  chemical: "Chemical",
  dosage_form: "Dosage form",
  route: "Route",
  intended_use: "Intended use",
  characteristic: "Characteristic",
  classification: "Classification",
  regulatory: "Regulatory",
  patent: "Patent",
  prior_art: "Prior art",
  traditional_knowledge: "Traditional knowledge",
  biological_resource: "Biological resource",
  abs: "Access & benefit sharing",
  evidence: "Evidence",
  action: "Next step",
  uncertainty: "Uncertainty",
};

export const STATUS_LABEL: Record<IdentityStatus, string> = {
  confirmed: "Confirmed",
  probable: "Probable",
  ambiguous: "Ambiguous",
  insufficient_evidence: "Insufficient evidence",
  human_review: "Human review",
};

const STATUS_STYLE: Record<IdentityStatus, string> = {
  confirmed: "bg-green-100 text-green-900 dark:bg-green-900/40 dark:text-green-200",
  probable: "bg-lime-100 text-lime-900 dark:bg-lime-900/40 dark:text-lime-200",
  ambiguous: "bg-amber-100 text-amber-900 dark:bg-amber-900/40 dark:text-amber-200",
  insufficient_evidence: "bg-neutral-200 text-neutral-700 dark:bg-neutral-800 dark:text-neutral-300",
  human_review: "bg-red-100 text-red-900 dark:bg-red-900/40 dark:text-red-200",
};

export const KIND_LABEL: Record<string, string> = {
  FACT_FROM_SOURCE: "Fact from source",
  MODEL_INTERPRETATION: "Model interpretation",
  CALCULATION: "Calculation",
  UNCERTAINTY: "Uncertainty",
};

const FGCard = memo(function FGCard({ data }: NodeProps<CardNode>) {
  const { fg, dimmed, focused, selected } = data;
  const uncertain = fg.type === "uncertainty" || fg.status === "ambiguous";
  const action = fg.type === "action";
  return (
    <div
      className={`w-[210px] rounded-md border border-l-4 bg-white px-2.5 py-2 text-left shadow-sm transition-all duration-200 dark:bg-neutral-900 ${
        BRANCH_ACCENT[fg.branch]
      } ${uncertain ? "border-dashed border-amber-400" : "border-neutral-200 dark:border-neutral-700"} ${
        action ? "bg-green-50 dark:bg-green-950/40" : ""
      } ${dimmed ? "opacity-25" : ""} ${focused ? "ring-2 ring-green-600 ring-offset-2 dark:ring-offset-neutral-950" : ""} ${
        selected && !focused ? "ring-2 ring-neutral-400" : ""
      }`}
    >
      <Handle type="target" position={Position.Left} className="!h-1.5 !w-1.5 !border-0 !bg-neutral-300" />
      <div className="text-[10px] font-medium uppercase tracking-wide text-neutral-500">{TYPE_LABEL[fg.type] ?? fg.type}</div>
      <div className={`truncate text-sm font-medium ${fg.type === "botanical_identity" ? "italic" : ""}`} title={fg.label}>
        {fg.label}
      </div>
      {fg.sublabel && (
        <div className="truncate text-[11px] text-neutral-500" title={fg.sublabel}>
          {fg.sublabel}
        </div>
      )}
      {(fg.status || fg.evidence_kind || fg.evidence_ids.length > 0) && (
        <div className="mt-1 flex flex-wrap items-center gap-1">
          {fg.status && (
            <span className={`rounded px-1.5 py-px text-[10px] font-medium ${STATUS_STYLE[fg.status]}`}>
              {STATUS_LABEL[fg.status]}
            </span>
          )}
          {fg.evidence_kind && (
            <span className="rounded border border-neutral-200 px-1 py-px text-[10px] text-neutral-500 dark:border-neutral-700">
              {KIND_LABEL[fg.evidence_kind]}
            </span>
          )}
          {fg.evidence_ids.length > 0 && (
            <span className="text-[10px] text-teal-700 dark:text-teal-400">
              {fg.evidence_ids.length} source{fg.evidence_ids.length === 1 ? "" : "s"}
            </span>
          )}
        </div>
      )}
      <Handle type="source" position={Position.Right} className="!h-1.5 !w-1.5 !border-0 !bg-neutral-300" />
    </div>
  );
});

const nodeTypes = { fg: FGCard };

function edgeStyle(type: string, status: string | null) {
  if (type === "requires_review" || status === "ambiguous" || status === "insufficient_evidence") {
    return { stroke: "#d97706", strokeDasharray: "5 4" };
  }
  if (type === "supported_by") return { stroke: "#0d9488" };
  if (type === "contradicted_by") return { stroke: "#dc2626" };
  if (type === "may_trigger" || type === "relevant_to") return { stroke: "#a3a3a3", strokeDasharray: "2 3" };
  return { stroke: "#a3a3a3" };
}

function MapInner({
  graph,
  ingredientOrder,
  filter,
  focusNodeId,
  selectedId,
  onSelect,
}: {
  graph: FormulationGraph;
  ingredientOrder: string[];
  filter: GraphFilter;
  focusNodeId: string | null;
  selectedId: string | null;
  onSelect: (node: FGNode | null) => void;
}) {
  const flow = useReactFlow();
  const positioned = useMemo(() => layoutGraph(graph, ingredientOrder), [graph, ingredientOrder]);
  const visible = useMemo(() => visibleNodeIds(graph, filter), [graph, filter]);
  const focus = useMemo(() => (focusNodeId ? neighbourhood(graph.edges, focusNodeId) : null), [graph, focusNodeId]);

  const nodes: CardNode[] = useMemo(
    () =>
      positioned.map(({ node, x, y }) => ({
        id: node.id,
        type: "fg",
        position: { x, y },
        draggable: false,
        data: {
          fg: node,
          dimmed: !visible.has(node.id) || (focus != null && !focus.nodes.has(node.id)),
          focused: node.id === focusNodeId,
          selected: node.id === selectedId,
        },
      })),
    [positioned, visible, focus, focusNodeId, selectedId],
  );

  const edges: Edge[] = useMemo(
    () =>
      graph.edges.map((e) => {
        const dim = !visible.has(e.source) || !visible.has(e.target) || (focus != null && !focus.edges.has(e.id));
        const style = edgeStyle(e.type, e.status);
        return {
          id: e.id,
          source: e.source,
          target: e.target,
          type: "smoothstep",
          label: e.type === "contains" || e.type === "leads_to" ? undefined : e.type.replace("_", " "),
          labelStyle: { fontSize: 9, fill: "#737373" },
          labelBgStyle: { fill: "transparent" },
          style: { ...style, strokeWidth: 1.25, opacity: dim ? 0.15 : 1 },
          markerEnd: { type: MarkerType.ArrowClosed, width: 12, height: 12, color: style.stroke },
        };
      }),
    [graph, visible, focus],
  );

  useEffect(() => {
    if (!focusNodeId) return;
    const target = positioned.find((p) => p.node.id === focusNodeId);
    if (target) flow.setCenter(target.x + 105, target.y + 30, { zoom: 1.1, duration: 500 });
  }, [focusNodeId, positioned, flow]);

  useEffect(() => {
    const t = setTimeout(() => flow.fitView({ padding: 0.15, duration: 300 }), 50);
    return () => clearTimeout(t);
  }, [graph.version, graph.formulation_id, flow]);

  return (
    <ReactFlow
      nodes={nodes}
      edges={edges}
      nodeTypes={nodeTypes}
      nodesConnectable={false}
      elementsSelectable
      onNodeClick={(_, n) => onSelect((n as CardNode).data.fg)}
      onPaneClick={() => onSelect(null)}
      fitView
      minZoom={0.2}
      maxZoom={1.8}
      proOptions={{ hideAttribution: true }}
    >
      <Background variant={BackgroundVariant.Dots} gap={18} size={1} color="#d4d4d4" />
      <Controls showInteractive={false} className="!shadow-none [&>button]:!border-neutral-200 [&>button]:!bg-white" />
    </ReactFlow>
  );
}

export function FormulationMap(props: Parameters<typeof MapInner>[0]) {
  return (
    <div className="h-[560px] w-full overflow-hidden rounded border border-neutral-200 bg-neutral-50 dark:border-neutral-800 dark:bg-neutral-950">
      <ReactFlowProvider>
        <MapInner {...props} />
      </ReactFlowProvider>
    </div>
  );
}
