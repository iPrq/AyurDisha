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
  LinkifiedText,
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
  IngredientInput,
  PdfUpload,
  Section,
  SourceScopeToggle,
  Sources,
  SubmitButton,
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

function cleanAnswer(text: string): string {
  if (!text) return "";
  return text
    .replace(/\(source_id=[^)]+\)/g, "")
    .replace(/Evidence source_ids?:[^\n]*/gi, "")
    .replace(/\[Unsupported claims were removed[^\]]*\]/gi, "")
    .replace(/\[fact from source\]/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
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
      {summary && <p className="text-sm">{cleanAnswer(summary)}</p>}
      {children}
    </Section>
  );
}

function Results({ r }: { r: ProductReviewResponse }) {
  const m = r.market_feasibility;
  const l = r.legal_compliance;
  const res = r.resource_accessibility;
  const terms = botanicalTerms(r.botanicals);

  const v = r.verification;
  const supported = v?.claims.filter((c) => c.status === "SUPPORTED") ?? [];
  const unsupported = v?.claims.filter((c) => c.status !== "SUPPORTED") ?? [];

  return (
    <div className="space-y-4">
      {/* Summary */}
      {(r.combined_summary || r.final_answer) && (
        <Section title="Summary">
          {r.combined_summary && (
            <div className="mb-4 text-sm text-neutral-600 dark:text-neutral-400">
              {cleanAnswer(r.combined_summary)}
            </div>
          )}
          {r.final_answer && (
            <div className="prose prose-sm dark:prose-invert max-w-none">
              <LinkifiedText extraTerms={terms} text={cleanAnswer(r.final_answer)} />
            </div>
          )}
          {r.disclaimer && (
            <div className="mt-4 text-xs text-neutral-500 italic">
              {cleanAnswer(r.disclaimer)}
            </div>
          )}
        </Section>
      )}

      {/* Verification */}
      {v && (
        <Section title="Verification" right={<Badge value={v.outcome} />}>
          <details className="group">
            <summary className="cursor-pointer text-sm font-medium hover:underline text-leaf list-none flex items-center justify-between">
              <span>{supported.length} supported &middot; {unsupported.length} unsupported claims</span>
            </summary>
            <div className="mt-4 space-y-4">
              {supported.length > 0 && (
                <div className="rounded-md border-l-4 border-green-500 bg-green-50/50 p-4 dark:bg-green-950/20">
                  <h4 className="text-sm font-medium text-green-800 dark:text-green-300 mb-2">Supported claims</h4>
                  <ul className="list-disc pl-5 text-sm space-y-1 text-green-900/80 dark:text-green-100/80">
                    {supported.map((c, i) => (
                      <li key={i}>{cleanAnswer(c.claim)}</li>
                    ))}
                  </ul>
                </div>
              )}
              {unsupported.length > 0 && (
                <div className="rounded-md border-l-4 border-red-500 bg-red-50/50 p-4 dark:bg-red-950/20">
                  <h4 className="text-sm font-medium text-red-800 dark:text-red-300 mb-2">Unsupported / Partial claims</h4>
                  <ul className="list-disc pl-5 text-sm space-y-1 text-red-900/80 dark:text-red-100/80">
                    {unsupported.map((c, i) => (
                      <li key={i}>{cleanAnswer(c.claim)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          </details>

          {v.stripped_unsupported_claims.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-xs text-muted hover:underline">
                {v.stripped_unsupported_claims.length} removed unsupported claim{v.stripped_unsupported_claims.length === 1 ? "" : "s"}
              </summary>
              <ul className="mt-2 list-disc pl-5 text-sm text-neutral-600 line-through dark:text-neutral-400">
                {v.stripped_unsupported_claims.map((c, i) => (
                  <li key={i}>{cleanAnswer(c)}</li>
                ))}
              </ul>
            </details>
          )}
        </Section>
      )}

      {m && (
        <Dimension title="Market feasibility" rating={m.rating} summary={m.summary}>
          {m.competitors?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {m.competitors.length} competitors</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {m.competitors.map((c, i) => (
                  <li key={i}>
                    <span className="font-medium">{c.name}</span>
                    {c.company && ` (${c.company})`}
                    {c.notes && ` - ${cleanAnswer(c.notes)}`}
                  </li>
                ))}
              </ul>
            </details>
          )}
          {m.demand_indicators?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {m.demand_indicators.length} demand indicators</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {m.demand_indicators.map((c, i) => (
                  <li key={i}>{cleanAnswer(c.summary)}</li>
                ))}
              </ul>
            </details>
          )}
          {m.findings?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {m.findings.length} findings</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {m.findings.map((c, i) => (
                  <li key={i}>{cleanAnswer(c.summary)}</li>
                ))}
              </ul>
            </details>
          )}
        </Dimension>
      )}

      {l && (
        <Dimension title="Legal compliance" rating={l.rating} summary={l.summary}>
          {l.regulatory_category && (
            <p className="mt-3 text-sm">
              <span className="font-medium">Regulatory category:</span>{" "}
              {l.regulatory_category}
            </p>
          )}
          {l.requirements?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {l.requirements.length} requirements</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {l.requirements.map((c, i) => (
                  <li key={i}>{cleanAnswer(c.summary)}</li>
                ))}
              </ul>
            </details>
          )}
          {l.restrictions?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {l.restrictions.length} restrictions</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {l.restrictions.map((c, i) => (
                  <li key={i}>{cleanAnswer(c.summary)}</li>
                ))}
              </ul>
            </details>
          )}
        </Dimension>
      )}

      {res && (
        <Dimension
          title="Resource accessibility"
          rating={res.rating}
          summary={res.summary}
        >
          {res.resources?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {res.resources.length} resources</summary>
              <ul className="mt-3 space-y-2 text-sm">
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
                    <div className="mt-1 text-neutral-600 dark:text-neutral-400">
                      {[
                        x.availability && `Availability: ${cleanAnswer(x.availability)}`,
                        x.cultivation && `Cultivation: ${cleanAnswer(x.cultivation)}`,
                        x.sustainability_concerns &&
                          `Sustainability: ${cleanAnswer(x.sustainability_concerns)}`,
                      ]
                        .filter(Boolean)
                        .join(" · ")}
                    </div>
                  </li>
                ))}
              </ul>
            </details>
          )}
          {res.findings?.length > 0 && (
            <details className="mt-3 group">
              <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">View {res.findings.length} findings</summary>
              <ul className="mt-3 list-disc pl-5 text-sm space-y-1">
                {res.findings.map((c, i) => (
                  <li key={i}>{cleanAnswer(c.summary)}</li>
                ))}
              </ul>
            </details>
          )}
        </Dimension>
      )}

      <Botanicals items={r.botanicals} />
      
      {r.retrieved_sources?.length > 0 && (
        <details className="group">
          <summary className="cursor-pointer text-sm font-medium text-leaf hover:underline">
            View {r.retrieved_sources.length} sources
          </summary>
          <div className="mt-4">
            <Sources items={r.retrieved_sources} terms={terms} />
          </div>
        </details>
      )}
    </div>
  );
}
