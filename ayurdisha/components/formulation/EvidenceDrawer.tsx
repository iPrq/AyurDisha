"use client";

import { Badge } from "@/components/ui";
import type { EvidenceItem, FGNode, FormulationGraph } from "@/lib/formulation/types";

const SCOPE: Record<string, string> = { domestic: "Indian", international: "International" };

/**
 * Retrieved sources with the verifier's verdict. Source text is shown exactly as retrieved —
 * never translated or paraphrased.
 */
export function EvidenceDrawer({
  graph,
  node,
  onClose,
  onShowAll,
}: {
  graph: FormulationGraph;
  node: FGNode | null;
  onClose: () => void;
  onShowAll: () => void;
}) {
  const items: EvidenceItem[] = node
    ? graph.evidence.filter((e) => node.evidence_ids.includes(e.source.id))
    : graph.evidence;

  return (
    <div className="space-y-3 rounded border border-teal-200 bg-white p-3 dark:border-teal-900 dark:bg-neutral-900">
      <div className="flex items-center justify-between gap-2">
        <div>
          <h3 className="font-semibold">Evidence</h3>
          <p className="text-xs text-neutral-500">
            {node ? `Sources cited by “${node.label}”` : `${graph.evidence.length} retrieved sources`}
            {node && (
              <button type="button" onClick={onShowAll} className="ml-2 underline">
                show all
              </button>
            )}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {graph.verification && <Badge value={graph.verification.outcome} />}
          <button type="button" onClick={onClose} className="text-neutral-400 hover:text-neutral-700" aria-label="Close evidence">
            ×
          </button>
        </div>
      </div>
      {items.length === 0 && (
        <p className="text-sm text-neutral-500">
          No retrieved source supports this yet. It is shown on the map as insufficient evidence.
        </p>
      )}
      <ul className="max-h-[420px] space-y-2 overflow-y-auto">
        {items.map((e) => (
          <li key={e.source.id} className="rounded border border-neutral-200 p-2 text-sm dark:border-neutral-800">
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge value={e.verifier_status} />
              <span className="rounded bg-neutral-100 px-1.5 text-[11px] dark:bg-neutral-800">{e.branch.replaceAll("_", " ")}</span>
              {e.source.legal_scope && (
                <span className="text-[11px] text-neutral-500">{SCOPE[e.source.legal_scope] ?? e.source.legal_scope}</span>
              )}
              {e.source.is_fixture && <span className="text-[11px] text-amber-700">(fixture)</span>}
            </div>
            <div className="mt-1 font-medium">{e.source.title}</div>
            <div className="text-xs text-neutral-500">
              <span className="font-mono">{e.source.id}</span>
              {e.source.section && ` · ${e.source.section}`} · {e.source.source_type}
            </div>
            {e.supports.length > 0 && (
              <ul className="mt-1 list-disc pl-4 text-xs text-teal-800 dark:text-teal-300">
                {e.supports.map((s, i) => (
                  <li key={i}>{s}</li>
                ))}
              </ul>
            )}
            <details className="mt-1">
              <summary className="cursor-pointer text-xs text-neutral-500">Source text (original)</summary>
              <p className="mt-1 whitespace-pre-wrap text-xs text-neutral-700 dark:text-neutral-300" lang="und">
                {e.source.text}
              </p>
            </details>
            {e.source.source_url && (
              <a href={e.source.source_url} target="_blank" rel="noreferrer" className="text-xs underline">
                Open source
              </a>
            )}
          </li>
        ))}
      </ul>
    </div>
  );
}
