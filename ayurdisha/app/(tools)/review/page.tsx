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
  formCardClass,
  inputClass,
} from "@/components/ui";
import { LoadingPanel } from "@/components/tool/LoadingPanel";
import { PageHero } from "@/components/tool/PageHero";
import { ResultsReveal } from "@/components/tool/ResultsReveal";
import { useSourceScope } from "@/components/site/SourceScope";

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
  const { scope: legalScope, setScope: setLegalScope } = useSourceScope();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ProductReviewResponse | null>(null);
  const [doc, setDoc] = useState<ProductDocumentExtractResponse | null>(null);
  const formRef = useRef({ product, ingredients, category, targetMarket, legalScope, query, doc });
  useEffect(() => {
    formRef.current = { product, ingredients, category, targetMarket, legalScope, query, doc };
  });

  const bridge = useToolBridge(
    "review",
    async ({ handlers, formulationId }) => {
      const f = formRef.current;
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await toolStreams.review(
          {
            product: f.product,
            ingredients: f.ingredients,
            legal_scope: f.legalScope,
            product_category: f.category || null,
            target_market: f.targetMarket || null,
            user_query: f.query || null,
            document_text: f.doc?.document_text ?? null,
            formulation_id: formulationId,
          },
          handlers,
        );
        setResult(r);
        const ratings = [
          r.market_feasibility && `market ${r.market_feasibility.rating.toLowerCase()}`,
          r.legal_compliance && `legal ${r.legal_compliance.rating.toLowerCase()}`,
          r.resource_accessibility && `resources ${r.resource_accessibility.rating.toLowerCase()}`,
        ].filter(Boolean);
        return { summary: `Review complete: ${ratings.join(", ").replaceAll("_", " ")}` };
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
      target_market: (v) => setTargetMarket(String(v)),
      legal_scope: (v) => setLegalScope(v as LegalScope),
    },
  );
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
        eyebrow="Product Review"
        title="Is my product ready for the market?"
        desc="Market feasibility, legal compliance and resource accessibility, each rated separately and backed by cited evidence."
        pose="inspect"
      />
      <ContextChip
        imported={bridge.imported}
        hasFormulation={!!bridge.formulation}
        currentVersion={bridge.formulation?.version ?? null}
        onImport={bridge.importNow}
        onDetach={bridge.detach}
      />

      <form onSubmit={onSubmit} className={formCardClass}>
        <PdfUpload
          label="Upload product document (PDF)"
          hint="Optional. Dossier, label or spec sheet; scanned PDFs are OCR'd. Extracted product, ingredients and category pre-fill the form below for review."
          doc={doc}
          extract={api.extractProductReviewDocument}
          onChange={onDoc}
          onError={setError}
          disabled={loading}
        />
        <FillRing active={bridge.filling === "product"}>
          <Field label="Product">
            <input
              required
              className={inputClass}
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="e.g. Ashwagandha stress-relief capsules"
            />
          </Field>
        </FillRing>
        <FillRing active={bridge.filling === "ingredients"}>
          <Field label="Ingredients">
            <IngredientInput value={ingredients} onChange={setIngredients} />
          </Field>
        </FillRing>
        <FillRing active={bridge.filling === "legal_scope"}>
          <SourceScopeToggle
            value={legalScope}
            onChange={setLegalScope}
            descriptions={SOURCE_DESCRIPTIONS}
          />
        </FillRing>
        <div className="grid gap-4 sm:grid-cols-2">
          <Field label="Product category" hint="Optional">
            <input
              className={inputClass}
              value={category}
              onChange={(e) => setCategory(e.target.value)}
              placeholder="e.g. health supplement"
            />
          </Field>
          <FillRing active={bridge.filling === "target_market"}>
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
