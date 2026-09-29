"use client";

import { useEffect, useRef, useState } from "react";
import {
  ContextChip,
  FillRing,
  StreamProgress,
  useToolBridge,
} from "@/components/formulation/ToolBridge";
import { api } from "@/lib/api";
import { toolStreams } from "@/lib/formulation/api";
import { botanicalTerms } from "@/components/knowledge-graph/KnowledgeGraphProvider";
import type {
  AbsPurpose,
  EntityType,
  NbaAbsResponse,
  ProductDocumentExtractResponse,
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
  PdfUpload,
  Section,
  SourceIds,
  Sources,
  SubmitButton,
  Verification,
  formCardClass,
  inputClass,
} from "@/components/ui";
import { LoadingPanel } from "@/components/tool/LoadingPanel";
import { PageHero } from "@/components/tool/PageHero";
import { ResultsReveal } from "@/components/tool/ResultsReveal";

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
  const [doc, setDoc] = useState<ProductDocumentExtractResponse | null>(null);
  const formRef = useRef({ product, ingredients, turnover, purpose, entityType, resourceSource, override, query });
  useEffect(() => {
    formRef.current = { product, ingredients, turnover, purpose, entityType, resourceSource, override, query };
  });

  const bridge = useToolBridge(
    "nba-abs",
    async ({ handlers, formulationId }) => {
      const f = formRef.current;
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await toolStreams.nbaAbs(
          {
            product: f.product,
            ingredients: f.ingredients,
            annual_turnover_inr: f.turnover ? Number(f.turnover) : null,
            purpose: f.purpose,
            entity_type: f.entityType,
            resource_source: f.resourceSource,
            percentage_override: f.override ? Number(f.override) : null,
            user_query: f.query || null,
            formulation_id: formulationId,
          },
          handlers,
        );
        setResult(r);
        const parts = [
          r.applicability && `applicability ${r.applicability.status.toLowerCase().replaceAll("_", " ")}`,
          r.calculation ? `fee ${inr(r.calculation.fee_inr)} (deterministic)` : "no fee calculated (turnover or rate not available)",
        ].filter(Boolean);
        return { summary: `ABS assessment complete: ${parts.join(", ")}` };
      } catch (err) {
        setError(err instanceof Error ? err.message : String(err));
        throw err;
      } finally {
        setLoading(false);
      }
    },
    {
      product: (v) => setProduct(String(v)),
      ingredients: (v) => setIngredients(v as string[]),
      purpose: (v) => setPurpose(v as AbsPurpose),
      entity_type: (v) => setEntityType(v as EntityType),
      resource_source: (v) => setResourceSource(v as ResourceSource),
    },
  );

  function onDoc(next: ProductDocumentExtractResponse | null) {
    setDoc(next);
    if (!next) return;
    if (next.product) setProduct(next.product);
    if (next.ingredients.length) setIngredients(next.ingredients);
  }

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
          formulation_id: bridge.imported?.formulationId ?? null,
        }),
      );
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-8">
      <PageHero
        eyebrow="NBA / ABS Calculator"
        title="Do I owe benefit sharing?"
        desc="Biological Diversity Act applicability, NBA approval requirements, benefit-sharing rate and fee calculation."
        pose="share"
      />
      <ContextChip
        imported={bridge.imported}
        hasFormulation={!!bridge.formulation}
        currentVersion={bridge.formulation?.version ?? null}
        onImport={bridge.importNow}
        onDetach={bridge.detach}
      />

      <form onSubmit={onSubmit} className={formCardClass}>
        <p className="rounded-2xl border border-line bg-mint/60 px-4 py-3 text-sm">
          <span className="font-semibold">Sources:</span> India{" "}
          <span className="text-xs text-muted">
            · Access and benefit sharing is governed by the Biological Diversity
            Act, 2002, so this tool always uses Indian law, whatever the header
            setting.
          </span>
        </p>
        <PdfUpload
          label="Upload product document (PDF)"
          hint="Optional. Only pre-fills product and ingredients below; the document is not sent with the calculation."
          doc={doc}
          extract={api.extractNbaAbsDocument}
          onChange={onDoc}
          onError={setError}
          disabled={loading}
          showText={false}
        />
        <FillRing active={bridge.filling === "product"}>
          <Field label="Product">
            <input
              required
              className={inputClass}
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="e.g. Brahmi memory tonic"
            />
          </Field>
        </FillRing>
        <FillRing active={bridge.filling === "ingredients"}>
          <Field label="Ingredients">
            <IngredientInput value={ingredients} onChange={setIngredients} />
          </Field>
        </FillRing>
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
          <FillRing active={bridge.filling === "purpose"}>
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
          </FillRing>
          <FillRing active={bridge.filling === "entity_type"}>
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
          </FillRing>
          <FillRing active={bridge.filling === "resource_source"}>
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
          </FillRing>
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

      <StreamProgress steps={bridge.steps} active={loading} />
      {error && <ErrorBanner message={error} />}
      {loading && <LoadingPanel />}
      {result && (
        <ResultsReveal>
          <Results r={result} />
        </ResultsReveal>
      )}
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
      <FinalAnswer
        answer={r.final_answer}
        disclaimer={r.disclaimer}
        terms={botanicalTerms(r.botanicals)}
      />
      <Verification v={r.verification} />
      <Sources items={r.retrieved_sources} terms={botanicalTerms(r.botanicals)} />
    </div>
  );
}
