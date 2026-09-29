"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useAgent } from "@/components/agent/AgentProvider";
import { registerTool, type ToolCapabilities } from "@/lib/agent/bus";
import type { StepEvent } from "@/lib/formulation/sse";
import type { ToolHandoff, ToolName } from "@/lib/formulation/types";

export interface ImportedContext {
  formulationId: string;
  version: number;
  name: string;
  filled: string[];
  derived: string[];
  botanicals: string[];
  ambiguous: string[];
}

export type StreamStep = { node: string; label: string; status: "running" | "completed" | "failed" };

const FILL_DELAY_MS = 220;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

/**
 * Formulation hand-off for a tool page: visible field-by-field autofill, the typed capability
 * registration the agent uses, and real stream progress. Manual use of the page is unaffected.
 */
export interface BridgeRunContext {
  handlers: {
    onStepStarted: (e: StepEvent) => void;
    onStepCompleted: (e: StepEvent) => void;
    onStepFailed: (e: StepEvent) => void;
  };
  formulationId: string | null;
}

export function useToolBridge(
  tool: ToolName,
  run: (ctx: BridgeRunContext) => Promise<{ summary: string }>,
  setters: Record<string, (value: unknown) => void>,
) {
  const { formulation, startToolRun } = useAgent();
  const [imported, setImported] = useState<ImportedContext | null>(null);
  const [filling, setFilling] = useState<string | null>(null);
  const [steps, setSteps] = useState<StreamStep[]>([]);
  const runRef = useRef(run);
  const settersRef = useRef(setters);
  const importedRef = useRef<ImportedContext | null>(null);

  useEffect(() => {
    runRef.current = run;
    settersRef.current = setters;
  });

  const autofill = useCallback(async (handoff: ToolHandoff) => {
    const filled: string[] = [];
    for (const [key, value] of Object.entries(handoff.fields)) {
      const set = settersRef.current[key];
      if (!set || value == null || value === "") continue;
      setFilling(key);
      set(value);
      filled.push(key);
      await sleep(FILL_DELAY_MS);
    }
    setFilling(null);
    const next: ImportedContext = {
      formulationId: handoff.formulation_id,
      version: handoff.version,
      name: handoff.summary.name ?? "Formulation",
      filled,
      derived: handoff.derived_fields,
      botanicals: handoff.summary.normalized_botanicals ?? [],
      ambiguous: handoff.summary.ambiguous ?? [],
    };
    importedRef.current = next;
    setImported(next);
    await sleep(0);
  }, []);

  /** Stream handlers that update both the page progress list and the agent timeline. */
  const trackProgress = useCallback(
    (progress?: Parameters<ToolCapabilities["run"]>[0]) => {
      setSteps([]);
      const upsert = (e: StepEvent, status: StreamStep["status"]) =>
        setSteps((s) =>
          s.some((x) => x.node === e.node)
            ? s.map((x) => (x.node === e.node ? { ...x, status } : x))
            : [...s, { node: e.node, label: e.label, status }],
        );
      return {
        onStepStarted: (e: StepEvent) => {
          upsert(e, "running");
          progress?.started(e);
        },
        onStepCompleted: (e: StepEvent) => {
          upsert(e, "completed");
          progress?.completed(e);
        },
        onStepFailed: (e: StepEvent) => {
          upsert(e, "failed");
          progress?.failed(e);
        },
      };
    },
    [],
  );

  useEffect(
    () =>
      registerTool(tool, {
        autofill,
        run: (progress) =>
          runRef.current({
            handlers: trackProgress(progress),
            formulationId: importedRef.current?.formulationId ?? null,
          }),
      }),
    [tool, autofill, trackProgress],
  );

  return {
    formulation,
    imported,
    detach: () => {
      importedRef.current = null;
      setImported(null);
    },
    filling,
    steps,
    importNow: () => startToolRun(tool, { run: false }),
  };
}

export function FillRing({ active, children }: { active: boolean; children: React.ReactNode }) {
  return (
    <div
      className={`rounded transition-shadow duration-200 ${active ? "ring-2 ring-green-500 ring-offset-2 dark:ring-offset-neutral-950" : ""}`}
    >
      {children}
    </div>
  );
}

const FIELD_LABEL: Record<string, string> = {
  product: "product",
  ingredients: "ingredients",
  legal_scope: "sources",
  target_market: "target market",
  purpose: "purpose",
  entity_type: "entity type",
  resource_source: "resource source",
};

export function ContextChip({
  imported,
  hasFormulation,
  currentVersion,
  onImport,
  onDetach,
}: {
  imported: ImportedContext | null;
  hasFormulation: boolean;
  currentVersion: number | null;
  onImport: () => void;
  onDetach: () => void;
}) {
  if (!imported) {
    if (!hasFormulation) return null;
    return (
      <button
        type="button"
        onClick={onImport}
        className="inline-flex items-center gap-2 rounded-full border border-dashed border-green-700 px-3 py-1 text-xs font-medium text-green-800 hover:bg-green-50 dark:text-green-400 dark:hover:bg-green-950"
      >
        Use formulation context{currentVersion ? ` (v${currentVersion})` : ""}
      </button>
    );
  }
  const outdated = currentVersion != null && currentVersion !== imported.version;
  return (
    <div className="space-y-1 rounded border border-green-200 bg-green-50 px-3 py-2 text-xs dark:border-green-900 dark:bg-green-950/40">
      <div className="flex flex-wrap items-center gap-2">
        <span className="rounded bg-green-800 px-1.5 py-0.5 text-[10px] font-bold tracking-wide text-white">FORMULATION CONTEXT</span>
        <span className="font-medium text-green-900 dark:text-green-100">{imported.name}</span>
        <span className="font-mono text-green-800 dark:text-green-300">v{imported.version}</span>
        {outdated && (
          <button type="button" onClick={onImport} className="text-amber-800 underline dark:text-amber-300">
            formulation is now v{currentVersion} — re-import
          </button>
        )}
        <button type="button" onClick={onDetach} className="ml-auto text-neutral-500 hover:text-red-600" title="Stop using formulation context">
          Detach
        </button>
      </div>
      <div className="text-green-900/80 dark:text-green-200/80">
        Filled: {imported.filled.map((f) => FIELD_LABEL[f] ?? f).join(", ") || "nothing"}
        {imported.derived.includes("product") && " · product name composed from ingredients"}
        {imported.botanicals.length > 0 && (
          <>
            {" · identities reused: "}
            <em>{imported.botanicals.join(", ")}</em>
          </>
        )}
        {imported.ambiguous.length > 0 && (
          <span className="text-amber-800 dark:text-amber-300"> · still ambiguous: {imported.ambiguous.join(", ")}</span>
        )}
      </div>
    </div>
  );
}

export function StreamProgress({ steps, active }: { steps: StreamStep[]; active: boolean }) {
  if (!active || !steps.length) return null;
  return (
    <ol className="space-y-1 rounded border border-neutral-200 p-3 text-xs dark:border-neutral-800" aria-label="Analysis progress">
      {steps.map((s) => (
        <li key={s.node} className="flex items-center gap-2">
          <span
            className={`h-1.5 w-1.5 rounded-full ${
              s.status === "completed" ? "bg-green-700" : s.status === "failed" ? "bg-red-600" : "animate-pulse bg-green-500"
            }`}
          />
          <span className={s.status === "running" ? "font-medium" : "text-neutral-600 dark:text-neutral-400"}>{s.label}</span>
        </li>
      ))}
    </ol>
  );
}
