"use client";

import { useState } from "react";
import { Field, inputClass } from "@/components/ui";
import { formulationApi } from "@/lib/formulation/api";
import { UNITS, type FormulationEnvelope, type IngredientInput } from "@/lib/formulation/types";

type Mode = "manual" | "text" | "pdf" | "patent_pdf";

const MODES: { id: Mode; label: string; hint: string }[] = [
  { id: "manual", label: "Manual", hint: "Enter ingredients yourself" },
  { id: "text", label: "Paste", hint: "Paste a label, spec or description" },
  { id: "pdf", label: "PDF", hint: "Formulation document (OCR fallback)" },
  { id: "patent_pdf", label: "Patent PDF", hint: "Extract the formulation from a patent" },
];

const emptyRow = (): IngredientInput => ({ user_term: "", quantity: null, unit: "mg", plant_part: null });

export function InputPanel({ onCreated }: { onCreated: (env: FormulationEnvelope) => void }) {
  const [mode, setMode] = useState<Mode>("manual");
  const [rows, setRows] = useState<IngredientInput[]>([emptyRow()]);
  const [name, setName] = useState("");
  const [dosageForm, setDosageForm] = useState("");
  const [intendedUse, setIntendedUse] = useState("");
  const [text, setText] = useState("");
  const [file, setFile] = useState<File | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const setRow = (i: number, patch: Partial<IngredientInput>) =>
    setRows((r) => r.map((row, j) => (j === i ? { ...row, ...patch } : row)));

  async function submit() {
    setLoading(true);
    setError(null);
    try {
      let env: FormulationEnvelope;
      if (mode === "manual") {
        const ingredients = rows.filter((r) => r.user_term.trim()).map((r) => ({ ...r, unit: r.quantity != null ? r.unit : null }));
        if (!ingredients.length) throw new Error("Add at least one ingredient.");
        env = await formulationApi.create({
          source_type: "manual",
          name: name || null,
          ingredients,
          dosage_form: dosageForm || null,
          intended_use: intendedUse || null,
        });
      } else if (mode === "text") {
        if (!text.trim()) throw new Error("Paste some formulation text first.");
        env = await formulationApi.create({ source_type: "text", raw_text: text });
      } else {
        if (!file) throw new Error("Choose a PDF first.");
        env = await formulationApi.upload(file, mode === "patent_pdf" ? "patent" : "formulation");
      }
      onCreated(env);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-4 rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <div role="tablist" aria-label="Input mode" className="inline-flex rounded border border-neutral-300 p-0.5 dark:border-neutral-700">
        {MODES.map((m) => (
          <button
            key={m.id}
            type="button"
            role="tab"
            aria-selected={mode === m.id}
            onClick={() => setMode(m.id)}
            className={`rounded px-3 py-1.5 text-sm font-medium ${
              mode === m.id ? "bg-green-700 text-white" : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
            }`}
          >
            {m.label}
          </button>
        ))}
      </div>
      <p className="text-xs text-neutral-500">
        {MODES.find((m) => m.id === mode)?.hint}. You can also describe it to the assistant (text or voice). Nothing is analyzed until you confirm the extraction.
      </p>

      {mode === "manual" && (
        <div className="space-y-3">
          <div className="space-y-2">
            {rows.map((r, i) => (
              <div key={i} className="grid grid-cols-[1fr_80px_80px_110px_24px] gap-2">
                <input
                  className={inputClass}
                  placeholder="Ingredient (e.g. Ashwagandha)"
                  value={r.user_term}
                  onChange={(e) => setRow(i, { user_term: e.target.value })}
                  aria-label={`Ingredient ${i + 1}`}
                />
                <input
                  className={inputClass}
                  type="number"
                  min={0}
                  placeholder="Qty"
                  value={r.quantity ?? ""}
                  onChange={(e) => setRow(i, { quantity: e.target.value === "" ? null : Number(e.target.value) })}
                  aria-label={`Quantity ${i + 1}`}
                />
                <select className={inputClass} value={r.unit ?? "mg"} onChange={(e) => setRow(i, { unit: e.target.value })} aria-label={`Unit ${i + 1}`}>
                  {UNITS.map((u) => (
                    <option key={u}>{u}</option>
                  ))}
                </select>
                <input
                  className={inputClass}
                  placeholder="Part"
                  value={r.plant_part ?? ""}
                  onChange={(e) => setRow(i, { plant_part: e.target.value || null })}
                  aria-label={`Plant part ${i + 1}`}
                />
                <button
                  type="button"
                  onClick={() => setRows((rs) => (rs.length > 1 ? rs.filter((_, j) => j !== i) : [emptyRow()]))}
                  className="text-neutral-400 hover:text-red-600"
                  aria-label={`Remove row ${i + 1}`}
                >
                  ×
                </button>
              </div>
            ))}
            <button type="button" onClick={() => setRows((r) => [...r, emptyRow()])} className="text-sm text-green-800 hover:underline dark:text-green-400">
              + Add ingredient
            </button>
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            <Field label="Name" hint="Optional">
              <input className={inputClass} value={name} onChange={(e) => setName(e.target.value)} />
            </Field>
            <Field label="Dosage form" hint="Optional">
              <input className={inputClass} value={dosageForm} onChange={(e) => setDosageForm(e.target.value)} placeholder="capsule" />
            </Field>
            <Field label="Intended use" hint="Optional">
              <input className={inputClass} value={intendedUse} onChange={(e) => setIntendedUse(e.target.value)} placeholder="stress support" />
            </Field>
          </div>
        </div>
      )}

      {mode === "text" && (
        <textarea
          className={inputClass}
          rows={6}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="e.g. Each capsule contains Ashwagandha root extract 300 mg and Turmeric 200 mg. For stress support."
        />
      )}

      {(mode === "pdf" || mode === "patent_pdf") && (
        <div className="space-y-1">
          <input
            type="file"
            accept="application/pdf"
            onChange={(e) => setFile(e.target.files?.[0] ?? null)}
            className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-green-700 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-green-800"
          />
          <p className="text-xs text-neutral-500">
            Text layer first, OCR for scanned pages. The document is used only for this formulation and is not added to the legal corpus.
          </p>
        </div>
      )}

      {error && <p className="text-sm text-red-700 dark:text-red-400">{error}</p>}
      <button
        type="button"
        onClick={submit}
        disabled={loading}
        className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800 disabled:opacity-50"
      >
        {loading ? (mode === "pdf" || mode === "patent_pdf" ? "Extracting (OCR may take a while)…" : "Extracting…") : "Extract formulation"}
      </button>
    </div>
  );
}
