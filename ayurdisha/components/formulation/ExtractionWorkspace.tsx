"use client";

import { useState } from "react";
import { inputClass } from "@/components/ui";
import type { AgentAction } from "@/lib/agent/actions";
import { formulationApi } from "@/lib/formulation/api";
import {
  UNITS,
  type ExtractionMeta,
  type FormulationContext,
  type FormulationIngredient,
  type IdentityStatus,
  type Unit,
  type VersionInfo,
} from "@/lib/formulation/types";
import { STATUS_LABEL } from "./FormulationMap";

const STATUS_TONE: Record<IdentityStatus, string> = {
  confirmed: "text-green-800 bg-green-100 dark:bg-green-900/40 dark:text-green-200",
  probable: "text-lime-900 bg-lime-100 dark:bg-lime-900/40 dark:text-lime-200",
  ambiguous: "text-amber-900 bg-amber-100 dark:bg-amber-900/40 dark:text-amber-200",
  insufficient_evidence: "text-neutral-700 bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300",
  human_review: "text-red-900 bg-red-100 dark:bg-red-900/40 dark:text-red-200",
};

const MISSING_LABEL: Record<string, string> = {
  ingredients: "ingredients",
  quantities: "some quantities",
  dosage_form: "dosage form",
  intended_use: "intended use",
  ambiguous_identity: "an ambiguous plant identity",
  unresolved_identity: "an unresolved identity",
};

function IngredientRow({
  ing,
  busy,
  apply,
}: {
  ing: FormulationIngredient;
  busy: boolean;
  apply: (a: AgentAction) => Promise<void>;
}) {
  const [qty, setQty] = useState(ing.quantity?.toString() ?? "");
  const [unit, setUnit] = useState<string>(ing.unit ?? "mg");
  const dirty = qty !== (ing.quantity?.toString() ?? "") || (qty !== "" && unit !== (ing.unit ?? "mg"));

  return (
    <li className="space-y-1.5 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{ing.user_term}</span>
        {ing.botanical_name && <em className="text-sm text-neutral-600 dark:text-neutral-400">{ing.botanical_name}</em>}
        <span className={`rounded px-1.5 py-0.5 text-[11px] font-medium ${STATUS_TONE[ing.identity_status]}`}>
          {STATUS_LABEL[ing.identity_status]}
          {ing.resolved_by_user && " · your choice"}
        </span>
        {ing.plant_part && <span className="text-xs text-neutral-500">{ing.plant_part}</span>}
        <div className="ml-auto flex items-center gap-1">
          <input
            className={`${inputClass} !w-20 !py-1`}
            type="number"
            min={0}
            value={qty}
            onChange={(e) => setQty(e.target.value)}
            aria-label={`Quantity of ${ing.user_term}`}
            placeholder="qty"
          />
          <select className={`${inputClass} !w-20 !py-1`} value={unit} onChange={(e) => setUnit(e.target.value)} aria-label={`Unit of ${ing.user_term}`}>
            {UNITS.map((u) => (
              <option key={u}>{u}</option>
            ))}
          </select>
          {dirty && (
            <button
              type="button"
              disabled={busy}
              onClick={() =>
                apply({
                  type: "UPDATE_INGREDIENT",
                  ingredient_id: ing.id,
                  quantity: qty === "" ? null : Number(qty),
                  unit: qty === "" ? null : (unit as Unit),
                })
              }
              className="rounded bg-green-700 px-2 py-1 text-xs text-white disabled:opacity-50"
            >
              Save
            </button>
          )}
          <button
            type="button"
            disabled={busy}
            onClick={() => apply({ type: "REMOVE_INGREDIENT", ingredient_id: ing.id })}
            className="px-1 text-neutral-400 hover:text-red-600"
            aria-label={`Remove ${ing.user_term}`}
          >
            ×
          </button>
        </div>
      </div>
      {ing.identity_status === "ambiguous" && ing.candidates.length > 0 && (
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-amber-800 dark:text-amber-300">Which plant?</span>
          {ing.candidates.map((c) => (
            <button
              key={c.botanical_name}
              type="button"
              disabled={busy}
              onClick={() => apply({ type: "RESOLVE_ENTITY", ingredient_id: ing.id, botanical_name: c.botanical_name })}
              className="rounded border border-amber-300 px-2 py-0.5 italic hover:bg-amber-50 disabled:opacity-50 dark:border-amber-800 dark:hover:bg-amber-950"
            >
              {c.botanical_name}
            </button>
          ))}
        </div>
      )}
      {ing.identity_status === "insufficient_evidence" && (
        <p className="text-xs text-neutral-500">No botanical identity could be established for this term; it is kept as you wrote it.</p>
      )}
      {ing.source_text && <p className="truncate text-[11px] text-neutral-400" title={ing.source_text}>from: “{ing.source_text}”</p>}
    </li>
  );
}

export function ExtractionWorkspace({
  ctx,
  extraction,
  onChange,
  onConfirmed,
}: {
  ctx: FormulationContext;
  extraction: ExtractionMeta | null;
  onChange: (ctx: FormulationContext, versions?: VersionInfo[]) => void;
  onConfirmed: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [newTerm, setNewTerm] = useState("");
  const [dosage, setDosage] = useState(ctx.dosage_form ?? "");
  const [use, setUse] = useState(ctx.intended_use ?? "");

  async function apply(action: AgentAction) {
    setBusy(true);
    setError(null);
    try {
      const res = await formulationApi.action(ctx.formulation_id, action, ctx.version);
      const env = await formulationApi.get(ctx.formulation_id);
      onChange(res.context, env.versions);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  async function confirm() {
    setBusy(true);
    setError(null);
    try {
      if (dosage.trim() && dosage.trim() !== (ctx.dosage_form ?? "")) {
        await formulationApi.action(ctx.formulation_id, { type: "UPDATE_DOSAGE_FORM", value: dosage.trim() });
      }
      if (use.trim() && use.trim() !== (ctx.intended_use ?? "")) {
        await formulationApi.action(ctx.formulation_id, { type: "UPDATE_INTENDED_USE", value: use.trim() });
      }
      const res = await formulationApi.confirm(ctx.formulation_id);
      const env = await formulationApi.get(ctx.formulation_id);
      onChange(res.context, env.versions);
      onConfirmed();
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setBusy(false);
    }
  }

  const missing = ctx.missing_information.map((m) => MISSING_LABEL[m] ?? m);
  const dropped = extraction?.dropped ?? [];

  return (
    <div className="space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <h2 className="font-semibold">{ctx.confirmed ? "Formulation" : "Review the extraction"}</h2>
        <span className="text-xs text-neutral-500">
          {ctx.source_type.replace("_", " ")} input
          {extraction?.method && ` · extracted by ${extraction.method}`}
          {extraction?.ocr_used && " · OCR used"}
        </span>
      </div>
      {!ctx.confirmed && (
        <p className="text-xs text-neutral-500">
          Check and edit what was extracted. Only text actually present in your input is kept; analysis starts after you confirm.
        </p>
      )}

      <ul className="divide-y divide-neutral-100 dark:divide-neutral-800">
        {ctx.ingredients.map((ing) => (
          <IngredientRow key={`${ing.id}-${ing.quantity}-${ing.unit}`} ing={ing} busy={busy} apply={apply} />
        ))}
      </ul>
      <form
        className="flex gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          if (!newTerm.trim()) return;
          void apply({ type: "ADD_INGREDIENT", user_term: newTerm.trim() }).then(() => setNewTerm(""));
        }}
      >
        <input className={inputClass} value={newTerm} onChange={(e) => setNewTerm(e.target.value)} placeholder="Add ingredient" />
        <button type="submit" disabled={busy} className="rounded border border-green-700 px-3 text-sm text-green-800 disabled:opacity-50 dark:text-green-400">
          Add
        </button>
      </form>

      <div className="grid gap-2 sm:grid-cols-2">
        <label className="space-y-1 text-sm">
          <span className="font-medium">Dosage form</span>
          <input className={inputClass} value={dosage} onChange={(e) => setDosage(e.target.value)} placeholder="not stated" />
        </label>
        <label className="space-y-1 text-sm">
          <span className="font-medium">Intended use</span>
          <input className={inputClass} value={use} onChange={(e) => setUse(e.target.value)} placeholder="not stated" />
        </label>
      </div>

      {missing.length > 0 && <p className="text-xs text-amber-800 dark:text-amber-300">Not stated: {missing.join(", ")}.</p>}
      {dropped.length > 0 && (
        <details className="text-xs text-neutral-500">
          <summary className="cursor-pointer">{dropped.length} extracted item(s) discarded because they were not in the source text</summary>
          <ul className="mt-1 list-disc pl-4">
            {dropped.map((d) => (
              <li key={d}>{d}</li>
            ))}
          </ul>
        </details>
      )}
      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
      {!ctx.confirmed && (
        <button
          type="button"
          onClick={confirm}
          disabled={busy || ctx.ingredients.length === 0}
          className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800 disabled:opacity-50"
        >
          Confirm and build map
        </button>
      )}
    </div>
  );
}
