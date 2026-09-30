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
import { botanicalTerms, LinkifiedText } from "@/components/knowledge-graph/KnowledgeGraphProvider";
import type {
  LegalScope,
  PatentAdvisorResponse,
  PatentDocumentExtractResponse,
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
    "Cites the Indian Patents Act 1970 (Section 3), CGPDTM examination guidelines, Indian patents and Indian case law.",
  international:
    "Cites US patent applications, the turmeric patent case and WIPO / EPO / USPTO web results. Indian Section 3 statute text is not retrieved.",
};

export default function PatentAdvisorPage() {
  const [product, setProduct] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([]);
  const { scope: legalScope, setScope: setLegalScope } = useSourceScope();
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PatentAdvisorResponse | null>(null);
  const [doc, setDoc] = useState<PatentDocumentExtractResponse | null>(null);
  const formRef = useRef({ product, ingredients, legalScope, query, doc });
  useEffect(() => {
    formRef.current = { product, ingredients, legalScope, query, doc };
  });

  const bridge = useToolBridge(
    "patent",
    async ({ handlers, formulationId }) => {
      const f = formRef.current;
      setLoading(true);
      setError(null);
      setResult(null);
      try {
        const r = await toolStreams.patent(
          {
            product: f.product,
            ingredients: f.ingredients,
            legal_scope: f.legalScope,
            user_query: f.query || null,
            document_text: f.doc?.document_text ?? null,
            formulation_id: formulationId,
          },
          handlers,
        );
        setResult(r);
        const triggered = r.patentability_risk?.triggered_clauses ?? [];
        const priorArt = r.prior_art?.findings.length ?? 0;
        const parts = [
          r.section3 && (triggered.length ? `Section 3 clauses flagged: ${triggered.join(", ")}` : "no Section 3 clause flagged"),
          `${priorArt} prior-art finding${priorArt === 1 ? "" : "s"}`,
        ].filter(Boolean);
        return { summary: `Patent analysis complete${parts.length ? `: ${parts.join(", ")}` : ""}` };
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
      legal_scope: (v) => setLegalScope(v as LegalScope),
    },
  );

  function onDoc(next: PatentDocumentExtractResponse | null) {
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
        await api.patentAdvisor({
          product,
          ingredients,
          legal_scope: legalScope,
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
        eyebrow="Patent Advisor"
        title="Can I patent this formulation?"
        desc="Indian Patents Act Section 3 risk indicator, prior art, grant likelihood and IP route suggestions."
        pose="proud"
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
          label="Upload disclosure (PDF)"
          hint="Optional. Scanned PDFs are OCR'd. Extracted product and ingredients pre-fill the form below for review."
          doc={doc}
          extract={api.extractPatentDocument}
          onChange={onDoc}
          onError={setError}
          disabled={loading}
        />

        <FillRing active={bridge.filling === "product"}>
          <Field label="Product / invention">
            <input
              required
              className={inputClass}
              value={product}
              onChange={(e) => setProduct(e.target.value)}
              placeholder="e.g. Turmeric-based anti-inflammatory gel"
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

/** Strip inline source_id references and evidence blocks the API embeds in final_answer text. */
function cleanAnswer(text: string): string {
  return text
    .replace(/\(source_id=[^)]+\)/g, "")
    .replace(/Evidence source_ids?:[^\n]*/gi, "")
    .replace(/\[Unsupported claims were removed[^\]]*\]/gi, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

const OFFICIAL_LINKS = [
  { href: "https://ipindia.gov.in/", label: "Patent Office (CGPDTM)" },
  { href: "https://ayush.gov.in/", label: "Ministry of AYUSH" },
  { href: "https://www.tkdl.res.in/", label: "TKDL Database" },
  { href: "https://nbaindia.org/", label: "National Biodiversity Authority" },
];

function Results({ r }: { r: PatentAdvisorResponse }) {
  const risk = r.patentability_risk;
  const s3 = r.section3;
  const grant = r.grant_likelihood;
  const v = r.verification;
  const terms = botanicalTerms([r.botanical]);

  const supported = v?.claims.filter((c) => c.status === "SUPPORTED") ?? [];
  const unsupported = v?.claims.filter((c) => c.status !== "SUPPORTED") ?? [];

  const needsReview =
    v?.outcome === "HUMAN_REVIEW_REQUIRED" ||
    (risk?.unweighted_triggered_clauses.length ?? 0) > 0;

  const flagged = s3?.provisions.filter((p) => p.triggered || p.evidence_gap) ?? [];
  const routes = r.ip_routes?.suggestions ?? [];
  const suitable = routes.filter((s) => s.appropriate);
  const notSuitable = routes.filter((s) => !s.appropriate);

  return (
    <div className="space-y-4">
      {needsReview && (
        <div className="space-y-3 rounded-3xl border border-turmeric/40 bg-turmeric/10 p-5 text-sm shadow-soft">
          <div className="flex items-center gap-3">
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-full bg-turmeric text-xl text-canvas shadow-inner">
              ⚠️
            </span>
            <h3 className="font-display text-lg font-bold text-[#8A520A]">
              Human expert review required
            </h3>
          </div>
          <p className="leading-relaxed text-[#8A520A] opacity-90">
            Some findings or Section 3 clauses need expert evaluation. This is decision support,
            not legal advice; consult a registered patent agent for definitive clearance.
          </p>
          <div className="flex flex-wrap gap-2">
            {OFFICIAL_LINKS.map((l) => (
              <a
                key={l.href}
                href={l.href}
                target="_blank"
                rel="noreferrer"
                className="inline-flex items-center gap-1 rounded-xl border border-line bg-surface px-4 py-2 font-medium text-leaf shadow-soft transition-transform hover:-translate-y-0.5 hover:text-leaf-bright"
              >
                {l.label} ↗
              </a>
            ))}
          </div>
        </div>
      )}

      {grant && (
        <Section
          title="Verdict"
          right={<Badge value={`${grant.confidence.toUpperCase()} CONFIDENCE`} />}
        >
          {grant.probability !== null ? (
            <div className="flex items-center gap-3">
              <span
                className={`font-mono text-4xl font-bold ${
                  grant.probability >= 0.6
                    ? "text-green-600"
                    : grant.probability >= 0.3
                      ? "text-amber-600"
                      : "text-red-600"
                }`}
              >
                {Math.round(grant.probability * 100)}%
              </span>
              <div className="flex-1 space-y-1">
                <div className="h-3 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
                  <div
                    className={`h-full transition-all ${
                      grant.probability >= 0.6
                        ? "bg-green-600"
                        : grant.probability >= 0.3
                          ? "bg-amber-500"
                          : "bg-red-500"
                    }`}
                    style={{ width: `${Math.round(grant.probability * 100)}%` }}
                  />
                </div>
                <span className="block text-xs text-muted">Estimated grant probability</span>
              </div>
            </div>
          ) : (
            <p className="text-sm text-amber-700">Not estimated — insufficient evidence.</p>
          )}
          <PreviewList title="Key factors" items={grant.key_factors} render={(f) => f} />
          {grant.rationale && (
            <MoreDetails label="Why this estimate">
              <p className="text-sm leading-relaxed">{grant.rationale}</p>
              <p className="text-xs text-neutral-500">{grant.disclaimer}</p>
            </MoreDetails>
          )}
        </Section>
      )}

      {risk && (
        <Section title="Section 3 risk">
          <div className="flex items-center gap-3">
            <div className="h-3 flex-1 overflow-hidden rounded-full bg-neutral-200 dark:bg-neutral-800">
              <div
                className={`h-full transition-all ${
                  risk.score >= 0.6
                    ? "bg-red-500"
                    : risk.score >= 0.3
                      ? "bg-amber-500"
                      : "bg-green-600"
                }`}
                style={{ width: `${Math.round(risk.score * 100)}%` }}
              />
            </div>
            <span className="font-mono text-sm">{risk.score.toFixed(2)}</span>
          </div>
          {s3?.summary && <p className="text-sm leading-relaxed">{s3.summary}</p>}

          {flagged.length > 0 ? (
            <PreviewList
              title="Flagged clauses"
              items={flagged}
              render={(p) => (
                <span>
                  <span className="font-mono font-semibold">{p.clause}</span>{" "}
                  <Badge value={p.triggered ? "TRIGGERED" : "EVIDENCE_GAP"} />{" "}
                  {p.reason}
                </span>
              )}
            />
          ) : (
            s3 && <p className="text-sm text-green-700">No Section 3 clause flagged.</p>
          )}

          {risk.unweighted_triggered_clauses.length > 0 && (
            <p className="text-sm text-amber-700">
              Also triggered (not weighted, needs human review):{" "}
              {risk.unweighted_triggered_clauses.join(", ")}
            </p>
          )}

          {s3 && s3.provisions.length > 0 && (
            <MoreDetails label="All provisions">
              <ul className="space-y-2 text-sm">
                {s3.provisions.map((p) => (
                  <li key={p.clause} className="flex gap-3">
                    <span className="w-12 shrink-0 font-mono font-medium">{p.clause}</span>
                    <span className="w-28 shrink-0">
                      {p.triggered ? (
                        <Badge value="TRIGGERED" />
                      ) : p.evidence_gap ? (
                        <Badge value="EVIDENCE_GAP" />
                      ) : (
                        <span className="text-xs text-neutral-500">not triggered</span>
                      )}
                    </span>
                    <span className="flex-1">{p.reason}</span>
                  </li>
                ))}
              </ul>
              {s3.rejected_clauses.length > 0 && (
                <p className="text-xs text-neutral-500">
                  Ignored unsupported clauses: {s3.rejected_clauses.join(", ")}
                </p>
              )}
              <p className="text-xs text-neutral-500">{risk.disclaimer}</p>
            </MoreDetails>
          )}
        </Section>
      )}

      {r.prior_art && (
        <Section title="Prior art">
          {r.prior_art.summary && (
            <p className="text-sm leading-relaxed">{r.prior_art.summary}</p>
          )}
          <PreviewList
            title="Findings"
            items={r.prior_art.findings}
            render={(f) => (
              <>
                {f.summary}
                {f.relevance && <span className="text-neutral-500"> ({f.relevance})</span>}
              </>
            )}
          />
        </Section>
      )}

      {r.ip_routes && (
        <Section title="IP routes">
          {r.ip_routes.summary && (
            <p className="text-sm leading-relaxed">{r.ip_routes.summary}</p>
          )}
          <PreviewList
            title="Recommended"
            items={suitable}
            limit={4}
            variant="cards"
            render={(s) => (
              <>
                <div className="font-semibold text-green-700">{s.route}</div>
                <div className="mt-1 text-xs text-neutral-600 dark:text-neutral-400">
                  {s.rationale}
                </div>
              </>
            )}
          />
          {notSuitable.length > 0 && (
            <MoreDetails label={`Not recommended (${notSuitable.length})`}>
              <ul className="space-y-2 text-sm">
                {notSuitable.map((s) => (
                  <li key={s.route}>
                    <span className="font-medium">{s.route}</span>
                    <div className="text-neutral-600 dark:text-neutral-400">{s.rationale}</div>
                  </li>
                ))}
              </ul>
            </MoreDetails>
          )}
        </Section>
      )}

      {r.botanical && <Botanicals items={[r.botanical]} />}

      {v && (
        <Section title="Verification" right={<Badge value={v.outcome} />}>
          <p className="text-sm">
            <span className="font-medium text-green-700">{supported.length} supported</span>
            {" · "}
            <span className="font-medium text-red-600">{unsupported.length} unsupported</span>
          </p>
          {v.escalation_reasons.length > 0 && (
            <PreviewList
              title="Escalation reasons"
              items={v.escalation_reasons}
              limit={2}
              render={(c) => c.replaceAll("_", " ")}
            />
          )}
          {(v.claims.length > 0 || v.stripped_unsupported_claims.length > 0) && (
            <MoreDetails label="View all claims">
              {supported.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Supported</SubHeading>
                  {supported.map((c, i) => (
                    <div key={i} className="border-l-2 border-green-500 pl-3 text-sm">
                      {c.claim}
                      {c.notes && <span className="block text-xs text-muted">{c.notes}</span>}
                    </div>
                  ))}
                </div>
              )}
              {unsupported.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Unsupported / partial</SubHeading>
                  {unsupported.map((c, i) => (
                    <div key={i} className="border-l-2 border-red-400 pl-3 text-sm">
                      <Badge value={c.status} /> <span>{c.claim}</span>
                      {c.notes && <span className="block text-xs text-muted">{c.notes}</span>}
                    </div>
                  ))}
                </div>
              )}
              {v.stripped_unsupported_claims.length > 0 && (
                <div className="space-y-1.5">
                  <SubHeading>Removed claims</SubHeading>
                  <ul className="list-disc pl-5 text-sm text-neutral-600 line-through dark:text-neutral-400">
                    {v.stripped_unsupported_claims.map((c, i) => (
                      <li key={i}>{c}</li>
                    ))}
                  </ul>
                </div>
              )}
              {v.notes && <p className="text-sm text-neutral-500">{v.notes}</p>}
            </MoreDetails>
          )}
        </Section>
      )}

      {r.final_answer && (
        <MoreDetails label="Full report">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            <LinkifiedText text={cleanAnswer(r.final_answer)} extraTerms={terms} />
          </p>
        </MoreDetails>
      )}
      <p className="text-xs text-neutral-500">{r.disclaimer}</p>

      <CollapsibleSources items={r.retrieved_sources} terms={terms} />
    </div>
  );
}
