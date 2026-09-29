"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type {
  AbsPurpose,
  EntityType,
  NbaAbsResponse,
  ResourceSource,
} from "@/lib/types";
import {
  Badge,
  Botanicals,
  ErrorBanner,
  Field,
  FinalAnswer,
  FindingList,
  IngredientInput,
  Section,
  SourceIds,
  Sources,
  SubmitButton,
  Verification,
  inputClass,
} from "@/components/ui";

const inr = (n: number) =>
  n.toLocaleString("en-IN", {
    style: "currency",
    currency: "INR",
    maximumFractionDigits: 2,
  });

export default function NbaAbsPage() {
  const [product, setProduct] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([]);
  const [turnover, setTurnover] = useState("");
  const [purpose, setPurpose] = useState<AbsPurpose>("commercial_utilization");
  const [entityType, setEntityType] = useState<EntityType>("indian");
  const [resourceSource, setResourceSource] =
    useState<ResourceSource>("unknown");
  const [override, setOverride] = useState("");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<NbaAbsResponse | null>(null);

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api.nbaAbs({
          product,
          ingredients,
          annual_turnover_inr: turnover ? Number(turnover) : null,
          purpose,
          entity_type: entityType,
          resource_source: resourceSource,
          percentage_override: override ? Number(override) : null,
          user_query: query || null,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">NBA / ABS Calculator</h1>

      <form onSubmit={onSubmit} className="space-y-4">
        <Field label="Product">
          <input
            required
            className={inputClass}
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="e.g. Brahmi memory tonic"
          />
        </Field>
        <Field label="Ingredients">
          <IngredientInput value={ingredients} onChange={setIngredients} />
        </Field>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Annual turnover (INR)" hint="Optional, needed for fee">
            <input
              type="number"
              min={0}
              className={inputClass}
              value={turnover}
              onChange={(e) => setTurnover(e.target.value)}
            />
          </Field>
          <Field
            label="Percentage override"
            hint="Optional, 0-100. Skips source rate selection."
          >
            <input
              type="number"
              min={0}
              max={100}
              step="any"
              className={inputClass}
              value={override}
              onChange={(e) => setOverride(e.target.value)}
            />
          </Field>
        </div>
        <div className="grid gap-4 sm:grid-cols-3">
          <Field label="Purpose">
            <select
              className={inputClass}
              value={purpose}
              onChange={(e) => setPurpose(e.target.value as AbsPurpose)}
            >
              <option value="commercial_utilization">
                Commercial utilization
              </option>
              <option value="research">Research</option>
              <option value="bio_survey">Bio-survey</option>
              <option value="ipr">IPR</option>
            </select>
          </Field>
          <Field label="Entity type">
            <select
              className={inputClass}
              value={entityType}
              onChange={(e) => setEntityType(e.target.value as EntityType)}
            >
              <option value="indian">Indian</option>
              <option value="foreign">Foreign</option>
            </select>
          </Field>
          <Field label="Resource source">
            <select
              className={inputClass}
              value={resourceSource}
              onChange={(e) =>
                setResourceSource(e.target.value as ResourceSource)
              }
            >
              <option value="unknown">Unknown</option>
              <option value="wild">Wild</option>
              <option value="cultivated">Cultivated</option>
            </select>
          </Field>
        </div>
        <Field label="Question" hint="Optional">
          <textarea
            className={inputClass}
            rows={2}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
        </Field>
        <SubmitButton loading={loading} />
      </form>

      {error && <ErrorBanner message={error} />}
      {result && <Results r={result} />}
    </div>
  );
}

function Results({ r }: { r: NbaAbsResponse }) {
  const a = r.applicability;
  const rate = r.rate_selection;
  const calc = r.calculation;
  return (
    <div className="space-y-4">
      {a && (
        <Section title="Applicability" right={<Badge value={a.status} />}>
          {a.authority && (
            <p className="text-sm">
              <span className="font-medium">Authority:</span> {a.authority}
            </p>
          )}
          {a.summary && <p className="text-sm">{a.summary}</p>}
          <FindingList title="Reasons" items={a.reasons} />
          <FindingList
            title="Exemptions considered"
            items={a.exemptions_considered}
          />
        </Section>
      )}

      {rate && (
        <Section
          title="Benefit-sharing rate"
          right={
            rate.percentage != null && (
              <span className="font-mono text-sm">{rate.percentage}%</span>
            )
          }
        >
          {rate.insufficient_evidence && (
            <p className="text-sm text-amber-700">
              Insufficient evidence to select a rate.
            </p>
          )}
          {rate.tier_description && (
            <p className="text-sm">{rate.tier_description}</p>
          )}
          {rate.basis && (
            <p className="text-sm">
              <span className="font-medium">Basis:</span> {rate.basis}
            </p>
          )}
          {rate.quoted_text && (
            <blockquote className="border-l-2 border-neutral-300 pl-3 text-sm italic text-neutral-600 dark:text-neutral-400">
              {rate.quoted_text}
              {rate.source_id && <SourceIds ids={[rate.source_id]} />}
            </blockquote>
          )}
          {rate.rationale && (
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              {rate.rationale}
            </p>
          )}
          <p className="text-xs text-neutral-500">
            {rate.grounded
              ? "Rate verified in cited source text."
              : "Rate not verified in source text."}
          </p>
        </Section>
      )}

      {calc && (
        <Section title="Fee calculation">
          <p className="text-2xl font-semibold">{inr(calc.fee_inr)}</p>
          <p className="text-sm">
            {inr(calc.annual_turnover_inr)} × {calc.percentage}% ÷ 100
          </p>
          <p className="text-xs text-neutral-500">
            {calc.formula} · rate from{" "}
            {calc.percentage_origin === "user_override"
              ? "your override"
              : "source"}
            {calc.source_id && <SourceIds ids={[calc.source_id]} />}
          </p>
        </Section>
      )}

      <Botanicals items={r.botanicals} />
      <FinalAnswer answer={r.final_answer} disclaimer={r.disclaimer} />
      <Verification v={r.verification} />
      <Sources items={r.retrieved_sources} />
    </div>
  );
}
