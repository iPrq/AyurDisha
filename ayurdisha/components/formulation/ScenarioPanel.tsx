"use client";

import { useState } from "react";
import { inputClass } from "@/components/ui";
import { formulationApi } from "@/lib/formulation/api";
import { UNITS, type FormulationContext, type ScenarioResult, type Unit } from "@/lib/formulation/types";

export function ScenarioPanel({
  ctx,
  scenario,
  onScenario,
}: {
  ctx: FormulationContext;
  scenario: ScenarioResult | null;
  onScenario: (s: ScenarioResult | null) => void;
}) {
  const [ingredientId, setIngredientId] = useState(ctx.ingredients[0]?.id ?? "");
  const [qty, setQty] = useState("");
  const [unit, setUnit] = useState<Unit>("mg");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function run() {
    if (!ingredientId || qty === "") return;
    setLoading(true);
    setError(null);
    try {
      onScenario(await formulationApi.scenario(ctx.formulation_id, [{ ingredient_id: ingredientId, quantity: Number(qty), unit }]));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-3 rounded border border-dashed border-neutral-300 p-3 dark:border-neutral-700">
      <h3 className="text-sm font-semibold">What if…</h3>
      <div className="flex flex-wrap gap-2">
        <select className={`${inputClass} !w-auto`} value={ingredientId} onChange={(e) => setIngredientId(e.target.value)} aria-label="Scenario ingredient">
          {ctx.ingredients.map((i) => (
            <option key={i.id} value={i.id}>
              {i.user_term}
            </option>
          ))}
        </select>
        <input className={`${inputClass} !w-24`} type="number" min={0} value={qty} onChange={(e) => setQty(e.target.value)} placeholder="qty" aria-label="Scenario quantity" />
        <select className={`${inputClass} !w-20`} value={unit} onChange={(e) => setUnit(e.target.value as Unit)} aria-label="Scenario unit">
          {UNITS.map((u) => (
            <option key={u}>{u}</option>
          ))}
        </select>
        <button type="button" onClick={run} disabled={loading || qty === ""} className="rounded border border-neutral-400 px-3 text-sm disabled:opacity-50">
          Model scenario
        </button>
      </div>
      {error && <p className="text-xs text-red-700">{error}</p>}
      {scenario && (
        <div className="space-y-2 rounded bg-amber-50 p-3 text-sm dark:bg-amber-950/30">
          <div className="flex items-center justify-between">
            <span className="text-xs font-bold tracking-wide text-amber-900 dark:text-amber-200">{scenario.banner}</span>
            <button type="button" onClick={() => onScenario(null)} className="text-xs text-neutral-500 hover:text-neutral-800">
              Dismiss
            </button>
          </div>
          <ul className="list-disc pl-4">
            {scenario.changes.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
          {scenario.potentially_affected.length > 0 && (
            <p className="text-xs">May need re-analysis: {scenario.potentially_affected.join(", ")}</p>
          )}
          <p className="text-xs text-neutral-600 dark:text-neutral-400">{scenario.note}</p>
        </div>
      )}
    </div>
  );
}
