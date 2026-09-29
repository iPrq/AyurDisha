"use client";

import { useMemo, useState } from "react";
import { useAgent } from "@/components/agent/AgentProvider";
import { EvidenceDrawer } from "@/components/formulation/EvidenceDrawer";
import { ExtractionWorkspace } from "@/components/formulation/ExtractionWorkspace";
import { FormulationMap } from "@/components/formulation/FormulationMap";
import { InputPanel } from "@/components/formulation/InputPanel";
import { NodeDetailPanel } from "@/components/formulation/NodeDetailPanel";
import { ScenarioPanel } from "@/components/formulation/ScenarioPanel";
import { VersionBar } from "@/components/formulation/VersionBar";
import type { GraphFilter } from "@/lib/agent/actions";
import { formulationApi } from "@/lib/formulation/api";
import type { StepEvent } from "@/lib/formulation/sse";
import type { ExtractionMeta, ToolName } from "@/lib/formulation/types";

const FILTERS: { id: GraphFilter; label: string }[] = [
  { id: "all", label: "All" },
  { id: "regulatory", label: "Regulatory" },
  { id: "patent", label: "Patent" },
  { id: "abs", label: "ABS" },
  { id: "evidence", label: "Evidence" },
];

const TOOLS: { tool: ToolName; label: string }[] = [
  { tool: "review", label: "Review Product" },
  { tool: "patent", label: "Analyze Patent" },
  { tool: "nba-abs", label: "Check ABS" },
];

type Sub = { node: string; label: string; status: "running" | "completed" | "failed" };

export default function FormulationPage() {
  const {
    formulation,
    versions,
    setFormulation,
    analysis,
    analysisStale,
    analyzing,
    analyzeNow,
    graphUi,
    setGraphUi,
    scenario,
    setScenario,
    comparison,
    startToolRun,
  } = useAgent();
  const [extraction, setExtraction] = useState<ExtractionMeta | null>(null);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [progress, setProgress] = useState<Sub[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [resolving, setResolving] = useState(false);
  const [editing, setEditing] = useState(false);

  const graph = analysis && formulation && analysis.graph.formulation_id === formulation.formulation_id ? analysis.graph : null;
  const ingredientOrder = useMemo(() => formulation?.ingredients.map((i) => i.id) ?? [], [formulation]);

  // An agent focus opens that node's WHY THIS MATTERS panel; a click selects without focusing.
  const activeId = graphUi.focusNodeId ?? selectedId;
  const selected = (graph && activeId ? graph.nodes.find((n) => n.id === activeId) : null) ?? null;

  const evidenceNode = graph && graphUi.evidenceNodeId ? graph.nodes.find((n) => n.id === graphUi.evidenceNodeId) ?? null : null;

  async function build() {
    setError(null);
    setProgress([]);
    const upsert = (e: StepEvent, status: Sub["status"]) =>
      setProgress((p) => (p.some((x) => x.node === e.node) ? p.map((x) => (x.node === e.node ? { ...x, status } : x)) : [...p, { node: e.node, label: e.label, status }]));
    try {
      await analyzeNow({
        started: (e) => upsert(e, "running"),
        completed: (e) => upsert(e, "completed"),
        failed: (e) => upsert(e, "failed"),
      });
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  async function resolve(ingredientId: string, botanicalName: string) {
    if (!formulation) return;
    setResolving(true);
    try {
      const res = await formulationApi.action(formulation.formulation_id, {
        type: "RESOLVE_ENTITY",
        ingredient_id: ingredientId,
        botanical_name: botanicalName,
      });
      const env = await formulationApi.get(formulation.formulation_id);
      setFormulation(res.context, env.versions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setResolving(false);
    }
  }

  function reset() {
    setFormulation(null, []);
    setExtraction(null);
    setSelectedId(null);
    setProgress([]);
    setGraphUi({ filter: "all", focusNodeId: null, evidenceOpen: false, evidenceNodeId: null });
  }

  return (
    <div className="relative left-1/2 w-[min(calc(100vw-2rem-var(--dock,0px)),1280px)] -translate-x-1/2 space-y-5">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Formulation Intelligence</h1>
          <p className="text-sm text-neutral-600 dark:text-neutral-400">
            One structured formulation shared by Product Review, Patent Advisor and NBA / ABS.
          </p>
        </div>
        {formulation && (
          <button type="button" onClick={reset} className="text-sm text-neutral-500 hover:text-neutral-800 dark:hover:text-neutral-200">
            Start a new formulation
          </button>
        )}
      </div>

      {!formulation && (
        <InputPanel
          onCreated={(env) => {
            setExtraction(env.extraction);
            setFormulation(env.context, env.versions);
          }}
        />
      )}

      {formulation && (
        <>
          <VersionBar ctx={formulation} versions={versions} external={comparison} />

          {(!formulation.confirmed || editing) && (
            <ExtractionWorkspace
              key={formulation.version}
              ctx={formulation}
              extraction={extraction}
              onChange={setFormulation}
              onConfirmed={() => {
                setEditing(false);
                void build();
              }}
            />
          )}

          {formulation.confirmed && (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <div role="radiogroup" aria-label="Map branch" className="inline-flex rounded border border-neutral-300 p-0.5 dark:border-neutral-700">
                  {FILTERS.map((f) => (
                    <button
                      key={f.id}
                      type="button"
                      role="radio"
                      aria-checked={graphUi.filter === f.id}
                      onClick={() => setGraphUi({ filter: f.id })}
                      className={`rounded px-3 py-1 text-xs font-medium ${
                        graphUi.filter === f.id ? "bg-green-700 text-white" : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
                {graphUi.focusNodeId && (
                  <button type="button" onClick={() => setGraphUi({ focusNodeId: null })} className="text-xs underline">
                    Clear focus
                  </button>
                )}
                {graph && (
                  <button
                    type="button"
                    onClick={() => setGraphUi({ evidenceOpen: true, evidenceNodeId: null })}
                    className="text-xs text-teal-700 underline dark:text-teal-400"
                  >
                    Evidence ({graph.evidence.length})
                  </button>
                )}
                <div className="ml-auto flex gap-2">
                  {!editing && (
                    <button type="button" onClick={() => setEditing(true)} className="rounded border border-neutral-300 px-3 py-1 text-xs dark:border-neutral-700">
                      Edit formulation
                    </button>
                  )}
                  <button
                    type="button"
                    onClick={() => void build()}
                    disabled={analyzing}
                    className="rounded border border-green-700 px-3 py-1 text-xs font-medium text-green-800 disabled:opacity-50 dark:text-green-400"
                  >
                    {analyzing ? "Building…" : graph ? "Rebuild map" : "Build map"}
                  </button>
                </div>
              </div>

              {analysisStale && !analyzing && (
                <div className="rounded border border-amber-300 bg-amber-50 px-3 py-2 text-xs text-amber-900 dark:border-amber-800 dark:bg-amber-950/40 dark:text-amber-200">
                  The formulation changed (now v{formulation.version}) since this map was built from v{analysis?.graph.version}.{" "}
                  <button type="button" className="font-medium underline" onClick={() => void build()}>
                    Rebuild map
                  </button>
                </div>
              )}
              {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}

              {analyzing && progress.length > 0 && (
                <ol className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-neutral-600 dark:text-neutral-400" aria-label="Analysis progress">
                  {progress.map((p) => (
                    <li key={p.node} className="flex items-center gap-1.5">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${p.status === "completed" ? "bg-green-700" : p.status === "failed" ? "bg-red-600" : "animate-pulse bg-green-500"}`}
                      />
                      {p.label}
                    </li>
                  ))}
                </ol>
              )}

              <div className="grid gap-4 lg:grid-cols-[1fr_340px]">
                <div>
                  {graph ? (
                    <FormulationMap
                      graph={graph}
                      ingredientOrder={ingredientOrder}
                      filter={graphUi.filter}
                      focusNodeId={graphUi.focusNodeId}
                      selectedId={selected?.id ?? null}
                      onSelect={(n) => {
                        setSelectedId(n?.id ?? null);
                        setGraphUi({ focusNodeId: null });
                      }}
                    />
                  ) : (
                    <div className="flex h-[560px] items-center justify-center rounded border border-dashed border-neutral-300 text-sm text-neutral-500 dark:border-neutral-700">
                      {analyzing ? "Building the formulation map…" : "Build the map to see identities, regulatory, patent and ABS branches."}
                    </div>
                  )}
                  {graph && <p className="mt-1 text-[11px] text-neutral-500">{graph.disclaimer}</p>}
                </div>

                <div className="space-y-3">
                  {graph && graphUi.evidenceOpen && (
                    <EvidenceDrawer
                      graph={graph}
                      node={evidenceNode}
                      onClose={() => setGraphUi({ evidenceOpen: false, evidenceNodeId: null })}
                      onShowAll={() => setGraphUi({ evidenceNodeId: null })}
                    />
                  )}
                  {selected && graph && (
                    <NodeDetailPanel
                      node={selected}
                      formulation={formulation}
                      onClose={() => {
                        setSelectedId(null);
                        setGraphUi({ focusNodeId: null });
                      }}
                      onOpenEvidence={(n) => setGraphUi({ evidenceOpen: true, evidenceNodeId: n.id })}
                      onRunTool={(tool) => startToolRun(tool)}
                      onResolve={resolve}
                      resolving={resolving}
                    />
                  )}
                  {!selected && !graphUi.evidenceOpen && (
                    <div className="space-y-2 rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
                      <h3 className="font-semibold">Characteristics</h3>
                      <ul className="space-y-1">
                        {formulation.formulation_characteristics.map((c) => (
                          <li key={c.key} className="flex justify-between gap-2">
                            <span className="text-neutral-500">{c.label}</span>
                            <span className="text-right">
                              {c.value}
                              <span className="ml-1 text-[10px] text-neutral-400">{c.origin === "user" ? "you" : c.evidence_kind?.toLowerCase().replaceAll("_", " ") ?? c.origin}</span>
                            </span>
                          </li>
                        ))}
                      </ul>
                      <p className="text-[11px] text-neutral-500">Click a node on the map to see why it matters.</p>
                    </div>
                  )}
                </div>
              </div>

              <div className="flex flex-wrap items-center gap-2 rounded border border-neutral-200 p-3 dark:border-neutral-800">
                <span className="mr-2 text-sm font-medium">Use this formulation in</span>
                {TOOLS.map(({ tool, label }) => {
                  const s = analysis?.suggested_actions.find((a) => a.tool === tool);
                  return (
                    <span key={tool} className="inline-flex items-center gap-1">
                      <button
                        type="button"
                        onClick={() => startToolRun(tool)}
                        className="rounded bg-green-700 px-3 py-1.5 text-sm font-medium text-white hover:bg-green-800"
                        title={s && !s.ready && s.question ? `Will ask: ${s.question}` : undefined}
                      >
                        {label}
                      </button>
                      <button
                        type="button"
                        onClick={() => startToolRun(tool, { run: false })}
                        className="rounded px-1.5 py-1.5 text-xs text-neutral-500 hover:bg-neutral-100 dark:hover:bg-neutral-800"
                        title="Open and prefill without running"
                      >
                        prefill only
                      </button>
                      {s && !s.ready && <span className="text-[11px] text-amber-700">needs {s.missing.join(", ") || "a choice"}</span>}
                    </span>
                  );
                })}
              </div>

              <ScenarioPanel key={formulation.version} ctx={formulation} scenario={scenario} onScenario={setScenario} />
            </>
          )}
        </>
      )}
    </div>
  );
}
