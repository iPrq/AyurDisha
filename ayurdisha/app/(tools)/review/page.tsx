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
  CollapsibleSources,
  ErrorBanner,
  Field,
  IngredientInput,
  MoreDetails,
  PdfUpload,
  PreviewList,
  Section,
  SourceScopeToggle,
  SubHeading,
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

const RATING_TEXT: Record<DimensionRating, string> = {
  FAVORABLE: "text-[#1E6B43] dark:text-leaf",
  MODERATE: "text-[#8A520A] dark:text-turmeric",
  CHALLENGING: "text-[#A5401A] dark:text-[#F4A585]",
  INSUFFICIENT_EVIDENCE: "text-muted",
};

function RatingTile({ label, rating }: { label: string; rating: DimensionRating | undefined }) {
  return (
    <div className="rounded-2xl border border-line bg-mint/40 p-4">
      <div className="text-xs font-semibold uppercase tracking-wider text-muted">{label}</div>
      <div className={`mt-1 font-display text-lg font-bold ${rating ? RATING_TEXT[rating] : "text-muted"}`}>
        {rating ? rating.replaceAll("_", " ").toLowerCase().replace(/^\w/, (c) => c.toUpperCase()) : "Not assessed"}
      </div>
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
      {summary && <p className="text-sm leading-relaxed">{cleanAnswer(summary)}</p>}
      {children}
    </Section>
  );
}

const findingText = (f: { summary: string }) => cleanAnswer(f.summary);

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
      <Section title="Overview">
        <div className="grid gap-3 sm:grid-cols-3">
          <RatingTile label="Market" rating={m?.rating} />
          <RatingTile label="Legal" rating={l?.rating} />
          <RatingTile label="Resources" rating={res?.rating} />
        </div>
        <p className="text-xs text-muted">
          Each dimension is rated independently; there is no combined score.
        </p>
      </Section>

      {m && (
        <Dimension title="Market feasibility" rating={m.rating} summary={m.summary}>
          <PreviewList
            title="Competitors"
            items={m.competitors}
            limit={4}
            variant="cards"
            render={(c) => (
              <>
                <div className="font-semibold">{c.name}</div>
                {c.company && <div className="text-xs text-muted">{c.company}</div>}
                {c.notes && (
                  <div className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
                    {cleanAnswer(c.notes)}
                  </div>
                )}
              </>
            )}
          />
          <PreviewList title="Findings" items={m.findings} render={findingText} />
          <PreviewList
            title="Demand indicators"
            items={m.demand_indicators}
            limit={2}
            render={findingText}
          />
          {m.target_category && (
            <p className="text-sm">
              <span className="font-semibold">Target category:</span> {m.target_category}
            </p>
          )}
        </Dimension>
      )}

      {l && (
        <Dimension title="Legal compliance" rating={l.rating} summary={l.summary}>
          {l.regulatory_category && (
            <div className="space-y-1">
              <SubHeading>Regulatory category</SubHeading>
              <p className="text-sm">{l.regulatory_category}</p>
            </div>
          )}
          <PreviewList title="Requirements" items={l.requirements} render={findingText} />
          <PreviewList title="Restrictions" items={l.restrictions} limit={2} render={findingText} />
        </Dimension>
      )}

      {res && (
        <Dimension title="Resource accessibility" rating={res.rating} summary={res.summary}>
          <PreviewList
            title="Ingredients"
            items={res.resources}
            limit={2}
            variant="cards"
            render={(x) => (
              <div className="space-y-1">
                <div>
                  <EntityLink
                    term={x.botanical_name ?? x.ingredient}
                    label="Herb"
                    className="font-semibold"
                  >
                    {x.ingredient}
                  </EntityLink>
                  {x.botanical_name && (
                    <em className="text-muted"> ({x.botanical_name})</em>
                  )}
                </div>
                {x.availability && (
                  <p className="text-xs">
                    <span className="font-semibold">Availability:</span>{" "}
                    {cleanAnswer(x.availability)}
                  </p>
                )}
                {(x.cultivation || x.sustainability_concerns) && (
                  <details className="text-xs">
                    <summary className="cursor-pointer font-medium text-leaf">
                      Cultivation & sustainability
                    </summary>
                    <div className="mt-1 space-y-1 text-neutral-600 dark:text-neutral-400">
                      {x.cultivation && <p>{cleanAnswer(x.cultivation)}</p>}
                      {x.sustainability_concerns && (
                        <p>{cleanAnswer(x.sustainability_concerns)}</p>
                      )}
                    </div>
                  </details>
                )}
              </div>
            )}
          />
          <PreviewList title="Findings" items={res.findings} render={findingText} />
        </Dimension>
      )}

      <Botanicals items={r.botanicals} />

      {v && (
        <Section title="Verification" right={<Badge value={v.outcome} />}>
          <p className="text-sm">
            <span className="font-medium text-green-700">{supported.length} supported</span>
            {" · "}
            <span className="font-medium text-red-600">{unsupported.length} unsupported</span>
          </p>
          {v.claims.length > 0 && (
            <MoreDetails label="View all claims">
              {supported.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Supported</SubHeading>
                  {supported.map((c, i) => (
                    <div key={i} className="border-l-2 border-green-500 pl-3 text-sm">
                      {cleanAnswer(c.claim)}
                    </div>
                  ))}
                </div>
              )}
              {unsupported.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Unsupported / partial</SubHeading>
                  {unsupported.map((c, i) => (
                    <div key={i} className="border-l-2 border-red-400 pl-3 text-sm">
                      {cleanAnswer(c.claim)}
                    </div>
                  ))}
                </div>
              )}
              {v.stripped_unsupported_claims.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Removed claims</SubHeading>
                  <ul className="list-disc pl-5 text-sm text-neutral-600 line-through dark:text-neutral-400">
                    {v.stripped_unsupported_claims.map((c, i) => (
                      <li key={i}>{cleanAnswer(c)}</li>
                    ))}
                  </ul>
                </div>
              )}
            </MoreDetails>
          )}
        </Section>
      )}

      {r.final_answer && (
        <MoreDetails label="Full report">
          <div className="whitespace-pre-wrap text-sm leading-relaxed">
            <LinkifiedText extraTerms={terms} text={cleanAnswer(r.final_answer)} />
          </div>
        </MoreDetails>
      )}
      {r.disclaimer && <p className="text-xs italic text-neutral-500">{cleanAnswer(r.disclaimer)}</p>}

      <CollapsibleSources items={r.retrieved_sources ?? []} terms={terms} />
    </div>
  );
}

