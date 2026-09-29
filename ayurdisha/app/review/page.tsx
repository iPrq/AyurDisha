"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import {
  botanicalTerms,
  EntityLink,
} from "@/components/knowledge-graph/KnowledgeGraphProvider";
import type {
  DimensionRating,
  LegalScope,
  ProductDocumentExtractResponse,
  ProductReviewResponse,
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
  SourceScopeToggle,
  Sources,
  SubmitButton,
  Verification,
  inputClass,
} from "@/components/ui";

const SOURCE_DESCRIPTIONS: Record<LegalScope, string> = {
  domestic:
    "Cites AYUSH, CDSCO, FSSAI and India Code for regulation, with Indian market and cultivation results.",
  international:
    "Cites WHO, FDA, EMA, EFSA, MHRA, TGA and Health Canada for regulation, with global market and IUCN / CITES results.",
};

export default function ProductReviewPage() {
  const [product, setProduct] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [targetMarket, setTargetMarket] = useState("");
  const [legalScope, setLegalScope] = useState<LegalScope>("domestic");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductReviewResponse | null>(null);
  const [doc, setDoc] = useState<ProductDocumentExtractResponse | null>(null);

  function onDoc(next: ProductDocumentExtractResponse | null) {
    setDoc(next);
    if (!next) return;
    if (next.product) setProduct(next.product);
    if (next.ingredients.length) setIngredients(next.ingredients);
    if (next.product_category) setCategory(next.product_category);
  }

  async function onSubmit(e: React.FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setResult(null);
    try {
      setResult(
        await api.productReview({
          product,
          ingredients,
          legal_scope: legalScope,
          product_category: category || null,
          target_market: targetMarket || null,
          user_query: query || null,
          document_text: doc?.document_text ?? null,
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
      <h1 className="text-xl font-semibold">Product Review</h1>

      <form onSubmit={onSubmit} className="space-y-4">
        <PdfUpload
          label="Upload product document (PDF)"
          hint="Optional. Dossier, label or spec sheet; scanned PDFs are OCR'd. Extracted product, ingredients and category pre-fill the form below for review."
          doc={doc}
          extract={api.extractProductReviewDocument}
          onChange={onDoc}
          onError={setError}
          disabled={loading}
        />
        <Field label="Product">
          <input
            required
            className={inputClass}
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="e.g. Ashwagandha stress-relief capsules"
          />
        </Field>
        <Field label="Ingredients">
          <IngredientInput value={ingredients} onChange={setIngredients} />
        </Field>
        <SourceScopeToggle
          value={legalScope}
          onChange={setLegalScope}
          descriptions={SOURCE_DESCRIPTIONS}
        />
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Product category" hint="Optional">
            <input
              className={inputClass}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. health supplement"
            />
          </Field>
          <Field
            label="Target market"
            hint={`Optional, defaults to ${legalScope === "international" ? "global" : "India"}`}
          >
            <input
              className={inputClass}
              value={targetMarket}
              onChange={(e) => setTargetMarket(e.target.value)}
            />
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

function Dimension({
  title,
  rating,
  summary,
  children,
}: {
  title: string;
  rating: DimensionRating;
  summary: string;
  children?: React.ReactNode;
}) {
  return (
    <Section title={title} right={<Badge value={rating} />}>
      {summary && <p className="text-sm">{summary}</p>}
      {children}
    </Section>
  );
}

function Results({ r }: { r: ProductReviewResponse }) {
  const m = r.market_feasibility;
  const l = r.legal_compliance;
  const res = r.resource_accessibility;
  return (
    <div className="space-y-4">
      {r.combined_summary && (
        <p className="rounded bg-neutral-100 p-3 text-sm dark:bg-neutral-900">
          {r.combined_summary}
        </p>
      )}

      {m && (
        <Dimension title="Market feasibility" rating={m.rating} summary={m.summary}>
          {m.competitors.length > 0 && (
            <div className="space-y-1">
              <h3 className="text-sm font-medium">Competitors</h3>
              <ul className="list-disc pl-5 text-sm">
                {m.competitors.map((c, i) => (
                  <li key={i}>
                    <span className="font-medium">{c.name}</span>
                    {c.company && ` (${c.company})`}
                    {c.notes && ` - ${c.notes}`}
                    <SourceIds ids={c.evidence_source_ids} />
                  </li>
                ))}
              </ul>
            </div>
          )}
          <FindingList title="Demand indicators" items={m.demand_indicators} />
          <FindingList title="Findings" items={m.findings} />
        </Dimension>
      )}

      {l && (
        <Dimension title="Legal compliance" rating={l.rating} summary={l.summary}>
          {l.regulatory_category && (
            <p className="text-sm">
              <span className="font-medium">Regulatory category:</span>{" "}
              {l.regulatory_category}
            </p>
          )}
          <FindingList title="Requirements" items={l.requirements} />
          <FindingList title="Restrictions" items={l.restrictions} />
        </Dimension>
      )}

      {res && (
        <Dimension
          title="Resource accessibility"
          rating={res.rating}
          summary={res.summary}
        >
          {res.resources.length > 0 && (
            <ul className="space-y-2 text-sm">
              {res.resources.map((x, i) => (
                <li key={i}>
                  <EntityLink
                    term={x.botanical_name ?? x.ingredient}
                    label="Herb"
                    className="font-medium"
                  >
                    {x.ingredient}
                  </EntityLink>
                  {x.botanical_name && <em> ({x.botanical_name})</em>}
                  <SourceIds ids={x.evidence_source_ids} />
                  <div className="text-neutral-600 dark:text-neutral-400">
                    {[
                      x.availability && `Availability: ${x.availability}`,
                      x.cultivation && `Cultivation: ${x.cultivation}`,
                      x.sustainability_concerns &&
                        `Sustainability: ${x.sustainability_concerns}`,
                    ]
                      .filter(Boolean)
                      .join(" · ")}
                  </div>
                </li>
              ))}
            </ul>
          )}
          <FindingList items={res.findings} />
        </Dimension>
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
