"use client";

import { useState } from "react";
import { api } from "@/lib/api";
import type {
  LegalScope,
  PatentAdvisorResponse,
  PatentDocumentExtractResponse,
} from "@/lib/types";
import {
  Badge,
  Botanicals,
  ErrorBanner,
  Field,
  FinalAnswer,
  IngredientInput,
  LegalScopeSelect,
  PdfUpload,
  Section,
  SourceIds,
  Sources,
  SubmitButton,
  Verification,
  inputClass,
} from "@/components/ui";

export default function PatentAdvisorPage() {
  const [product, setProduct] = useState("");
  const [ingredients, setIngredients] = useState<string[]>([]);
  const [legalScope, setLegalScope] = useState<LegalScope>("domestic");
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PatentAdvisorResponse | null>(null);
  const [doc, setDoc] = useState<PatentDocumentExtractResponse | null>(null);

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
      <h1 className="text-xl font-semibold">Patent Advisor</h1>

      <form onSubmit={onSubmit} className="space-y-4">
        <PdfUpload
          label="Upload disclosure (PDF)"
          hint="Optional. Scanned PDFs are OCR'd. Extracted product and ingredients pre-fill the form below for review."
          doc={doc}
          extract={api.extractPatentDocument}
          onChange={onDoc}
          onError={setError}
          disabled={loading}
        />

        <Field label="Product / invention">
          <input
            required
            className={inputClass}
            value={product}
            onChange={(e) => setProduct(e.target.value)}
            placeholder="e.g. Turmeric-based anti-inflammatory gel"
          />
        </Field>
        <Field label="Ingredients">
          <IngredientInput value={ingredients} onChange={setIngredients} />
        </Field>
        <Field label="Legal scope">
          <LegalScopeSelect value={legalScope} onChange={setLegalScope} />
        </Field>
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

function Results({ r }: { r: PatentAdvisorResponse }) {
  const risk = r.patentability_risk;
  const s3 = r.section3;
  const grant = r.grant_likelihood;
  return (
    <div className="space-y-4">
      {grant && (
        <Section
          title="Estimated grant probability"
          right={<Badge value={`${grant.confidence.toUpperCase()} CONFIDENCE`} />}
        >
          {grant.probability !== null ? (
            <div className="flex items-center gap-3">
              <span
                className={`font-mono text-3xl font-semibold ${
                  grant.probability >= 0.6
                    ? "text-green-600"
                    : grant.probability >= 0.3
                      ? "text-amber-600"
                      : "text-red-600"
                }`}
              >
                {Math.round(grant.probability * 100)}%
              </span>
              <div className="h-3 flex-1 overflow-hidden rounded bg-neutral-200 dark:bg-neutral-800">
                <div
                  className={`h-full ${
                    grant.probability >= 0.6
                      ? "bg-green-600"
                      : grant.probability >= 0.3
                        ? "bg-amber-500"
                        : "bg-red-500"
                  }`}
                  style={{ width: `${Math.round(grant.probability * 100)}%` }}
                />
              </div>
            </div>
          ) : (
            <p className="text-sm text-amber-700">
              Not estimated — insufficient evidence.
            </p>
          )}
          {grant.key_factors.length > 0 && (
            <ul className="list-disc space-y-1 pl-5 text-sm">
              {grant.key_factors.map((f, i) => (
                <li key={i}>{f}</li>
              ))}
            </ul>
          )}
          {grant.rationale && (
            <p className="text-sm">
              {grant.rationale}
              <SourceIds ids={grant.evidence_source_ids} />
            </p>
          )}
          <p className="text-xs text-neutral-500">{grant.disclaimer}</p>
        </Section>
      )}

      {risk && (
        <Section title="Section 3 risk score (rule-based)">
          <div className="flex items-center gap-3">
            <div className="h-3 flex-1 overflow-hidden rounded bg-neutral-200 dark:bg-neutral-800">
              <div
                className={`h-full ${
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
          {risk.triggered_clauses.length > 0 && (
            <p className="text-sm">
              Triggered clauses: {risk.triggered_clauses.join(", ")}
            </p>
          )}
          {risk.unweighted_triggered_clauses.length > 0 && (
            <p className="text-sm text-amber-700">
              Also triggered (not weighted, needs human review):{" "}
              {risk.unweighted_triggered_clauses.join(", ")}
            </p>
          )}
          <p className="text-xs text-neutral-500">{risk.disclaimer}</p>
        </Section>
      )}

      {s3 && (
        <Section title="Section 3 analysis">
          {s3.summary && <p className="text-sm">{s3.summary}</p>}
          <ul className="space-y-2 text-sm">
            {s3.provisions.map((p) => (
              <li key={p.clause} className="flex gap-3">
                <span className="w-12 shrink-0 font-mono font-medium">
                  {p.clause}
                </span>
                <span className="w-28 shrink-0">
                  {p.triggered ? (
                    <Badge value="TRIGGERED" />
                  ) : p.evidence_gap ? (
                    <Badge value="EVIDENCE_GAP" />
                  ) : (
                    <span className="text-xs text-neutral-500">
                      not triggered
                    </span>
                  )}
                </span>
                <span className="flex-1">
                  {p.reason}
                  <SourceIds ids={p.evidence_source_ids} />
                </span>
              </li>
            ))}
          </ul>
          {s3.rejected_clauses.length > 0 && (
            <p className="text-xs text-neutral-500">
              Ignored unsupported clauses: {s3.rejected_clauses.join(", ")}
            </p>
          )}
        </Section>
      )}

      {r.prior_art && (
        <Section title="Prior art">
          {r.prior_art.summary && (
            <p className="text-sm">{r.prior_art.summary}</p>
          )}
          <ul className="list-disc space-y-1 pl-5 text-sm">
            {r.prior_art.findings.map((f, i) => (
              <li key={i}>
                {f.summary}
                {f.relevance && (
                  <span className="text-neutral-500"> ({f.relevance})</span>
                )}
                <SourceIds ids={f.evidence_source_ids} />
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.ip_routes && (
        <Section title="IP routes">
          {r.ip_routes.summary && (
            <p className="text-sm">{r.ip_routes.summary}</p>
          )}
          <ul className="space-y-2 text-sm">
            {r.ip_routes.suggestions.map((s) => (
              <li key={s.route}>
                <span className="font-medium">{s.route}</span>{" "}
                <span
                  className={
                    s.appropriate ? "text-green-700" : "text-neutral-500"
                  }
                >
                  {s.appropriate ? "- suitable" : "- not suitable"}
                </span>
                <div className="text-neutral-600 dark:text-neutral-400">
                  {s.rationale}
                  <SourceIds ids={s.evidence_source_ids} />
                </div>
              </li>
            ))}
          </ul>
        </Section>
      )}

      {r.botanical && <Botanicals items={[r.botanical]} />}
      <FinalAnswer answer={r.final_answer} disclaimer={r.disclaimer} />
      <Verification v={r.verification} />
      <Sources items={r.retrieved_sources} />
    </div>
  );
}
