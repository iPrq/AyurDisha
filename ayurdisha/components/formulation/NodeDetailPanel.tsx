"use client";

import type { ToolName } from "@/lib/formulation/types";
import type { FGNode, FormulationContext } from "@/lib/formulation/types";
import { KIND_LABEL, STATUS_LABEL } from "./FormulationMap";

const ACTION_TOOL: Record<string, ToolName> = {
  RUN_PRODUCT_REVIEW: "review",
  RUN_PATENT_ADVISOR: "patent",
  RUN_ABS: "nba-abs",
};

function Block({ title, tone, items }: { title: string; tone: string; items: string[] }) {
  if (!items.length) return null;
  return (
    <div className="space-y-1">
      <div className={`text-[10px] font-semibold uppercase tracking-wide ${tone}`}>{title}</div>
      <ul className="space-y-1 text-sm">
        {items.map((t, i) => (
          <li key={i} className="leading-snug">
            {t}
          </li>
        ))}
      </ul>
    </div>
  );
}

export function NodeDetailPanel({
  node,
  formulation,
  onClose,
  onOpenEvidence,
  onRunTool,
  onResolve,
  resolving,
}: {
  node: FGNode;
  formulation: FormulationContext | null;
  onClose: () => void;
  onOpenEvidence: (node: FGNode) => void;
  onRunTool: (tool: ToolName) => void;
  onResolve: (ingredientId: string, botanicalName: string) => void;
  resolving: boolean;
}) {
  const why = node.why_it_matters;
  const ingredient = node.ref ? formulation?.ingredients.find((i) => i.id === node.ref) : undefined;
  const canResolve = ingredient && ingredient.identity_status === "ambiguous" && ingredient.candidates.length > 0;
  const tool = node.type === "action" && node.ref ? ACTION_TOOL[node.ref] : undefined;

  return (
    <div className="space-y-3 rounded border border-neutral-200 bg-white p-3 dark:border-neutral-800 dark:bg-neutral-900">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="text-[10px] uppercase tracking-wide text-neutral-500">{node.type.replaceAll("_", " ")}</div>
          <h3 className={`font-semibold ${node.type === "botanical_identity" ? "italic" : ""}`}>{node.label}</h3>
          {node.sublabel && <p className="text-xs text-neutral-500">{node.sublabel}</p>}
        </div>
        <button type="button" onClick={onClose} className="text-neutral-400 hover:text-neutral-700" aria-label="Close details">
          ×
        </button>
      </div>
      <div className="flex flex-wrap gap-1.5 text-[11px]">
        {node.status && <span className="rounded bg-neutral-100 px-1.5 py-0.5 dark:bg-neutral-800">{STATUS_LABEL[node.status]}</span>}
        {node.evidence_kind && (
          <span className="rounded border border-neutral-200 px-1.5 py-0.5 dark:border-neutral-700">{KIND_LABEL[node.evidence_kind]}</span>
        )}
      </div>

      {why && (why.facts.length > 0 || why.interpretation.length > 0 || why.uncertainty.length > 0) && (
        <section className="space-y-2 border-t border-neutral-100 pt-2 dark:border-neutral-800">
          <h4 className="text-xs font-semibold uppercase tracking-wide text-green-800 dark:text-green-400">Why this matters</h4>
          <Block title="Fact from source" tone="text-teal-700 dark:text-teal-400" items={why.facts} />
          <Block title="Model interpretation" tone="text-violet-700 dark:text-violet-400" items={why.interpretation} />
          <Block title="Uncertainty" tone="text-amber-700 dark:text-amber-400" items={why.uncertainty} />
        </section>
      )}

      {canResolve && (
        <section className="space-y-1.5 border-t border-neutral-100 pt-2 dark:border-neutral-800">
          <h4 className="text-xs font-semibold">Which plant do you mean by “{ingredient.user_term}”?</h4>
          <p className="text-[11px] text-neutral-500">Nothing is picked automatically. Your choice is recorded as user-selected, not as a sourced fact.</p>
          <div className="flex flex-wrap gap-1.5">
            {ingredient.candidates.map((c) => (
              <button
                key={c.botanical_name}
                type="button"
                disabled={resolving}
                onClick={() => onResolve(ingredient.id, c.botanical_name)}
                className="rounded border border-amber-300 px-2 py-1 text-xs italic hover:bg-amber-50 disabled:opacity-50 dark:border-amber-800 dark:hover:bg-amber-950"
              >
                {c.botanical_name}
              </button>
            ))}
          </div>
        </section>
      )}

      <div className="flex flex-wrap gap-2 border-t border-neutral-100 pt-2 dark:border-neutral-800">
        {node.evidence_ids.length > 0 && (
          <button
            type="button"
            onClick={() => onOpenEvidence(node)}
            className="rounded border border-teal-600 px-2 py-1 text-xs font-medium text-teal-700 hover:bg-teal-50 dark:text-teal-300 dark:hover:bg-teal-950"
          >
            View {node.evidence_ids.length} source{node.evidence_ids.length === 1 ? "" : "s"}
          </button>
        )}
        {tool && (
          <button
            type="button"
            onClick={() => onRunTool(tool)}
            className="rounded bg-green-700 px-2 py-1 text-xs font-medium text-white hover:bg-green-800"
          >
            {node.label}
          </button>
        )}
      </div>
    </div>
  );
}
