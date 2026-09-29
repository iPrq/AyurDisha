"use client";

import { useRef, useState } from "react";
import {
  EntityLink,
  LinkifiedText,
} from "@/components/knowledge-graph/KnowledgeGraphProvider";
import type {
  BotanicalResult,
  DocumentExtractResponse,
  LegalScope,
  RetrievedSource,
  ReviewFinding,
  VerificationResult,
} from "@/lib/types";

export const inputClass =
  "w-full rounded border border-neutral-300 bg-white px-3 py-2 text-sm focus:border-green-700 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900";

export function Field({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <label className="block space-y-1">
      <span className="text-sm font-medium">{label}</span>
      {children}
      {hint && <span className="block text-xs text-neutral-500">{hint}</span>}
    </label>
  );
}

export function IngredientInput({
  value,
  onChange,
}: {
  value: string[];
  onChange: (v: string[]) => void;
}) {
  const [draft, setDraft] = useState("");
  const add = () => {
    const items = draft
      .split(",")
      .map((s) => s.trim())
      .filter((s) => s && !value.includes(s));
    if (items.length) onChange([...value, ...items]);
    setDraft("");
  };
  return (
    <div className="space-y-2">
      <input
        className={inputClass}
        value={draft}
        placeholder="e.g. Ashwagandha, Tulsi (press Enter)"
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === ",") {
            e.preventDefault();
            add();
          }
        }}
        onBlur={add}
      />
      {value.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {value.map((v) => (
            <span
              key={v}
              className="flex items-center gap-1 rounded bg-green-100 px-2 py-0.5 text-sm text-green-900 dark:bg-green-900/40 dark:text-green-100"
            >
              {v}
              <button
                type="button"
                className="text-green-700 hover:text-red-600"
                onClick={() => onChange(value.filter((x) => x !== v))}
                aria-label={`Remove ${v}`}
              >
                ×
              </button>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

const SCOPE_LABELS: Record<LegalScope, string> = {
  domestic: "Indian",
  international: "International",
};

export function SourceScopeToggle({
  value,
  onChange,
  descriptions,
}: {
  value: LegalScope;
  onChange: (v: LegalScope) => void;
  descriptions: Record<LegalScope, string>;
}) {
  return (
    <div className="space-y-1">
      <span className="block text-sm font-medium">Sources</span>
      <div
        role="radiogroup"
        aria-label="Sources"
        className="inline-flex rounded border border-neutral-300 p-0.5 dark:border-neutral-700"
      >
        {(Object.keys(SCOPE_LABELS) as LegalScope[]).map((scope) => (
          <button
            key={scope}
            type="button"
            role="radio"
            aria-checked={value === scope}
            onClick={() => onChange(scope)}
            className={`rounded px-4 py-1.5 text-sm font-medium transition-colors ${
              value === scope
                ? "bg-green-700 text-white"
                : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
            }`}
          >
            {SCOPE_LABELS[scope]}
          </button>
        ))}
      </div>
      <span className="block text-xs text-neutral-500">
        {descriptions[value]}
      </span>
    </div>
  );
}

export function SubmitButton({ loading }: { loading: boolean }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="rounded bg-green-700 px-4 py-2 text-sm font-medium text-white hover:bg-green-800 disabled:opacity-50"
    >
      {loading ? "Analyzing... (this can take a minute)" : "Run analysis"}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="rounded border border-red-300 bg-red-50 p-3 text-sm text-red-800 dark:border-red-800 dark:bg-red-950 dark:text-red-200">
      {message}
    </div>
  );
}

const BADGE_COLORS: Record<string, string> = {
  FAVORABLE: "bg-green-100 text-green-900",
  PASS: "bg-green-100 text-green-900",
  RESOLVED: "bg-green-100 text-green-900",
  SUPPORTED: "bg-green-100 text-green-900",
  NOT_APPLICABLE: "bg-green-100 text-green-900",
  MODERATE: "bg-amber-100 text-amber-900",
  AMBIGUOUS: "bg-amber-100 text-amber-900",
  PARTIALLY_SUPPORTED: "bg-amber-100 text-amber-900",
  UNCERTAIN: "bg-amber-100 text-amber-900",
  HUMAN_REVIEW_REQUIRED: "bg-amber-100 text-amber-900",
  CHALLENGING: "bg-red-100 text-red-900",
  FAIL: "bg-red-100 text-red-900",
  UNSUPPORTED: "bg-red-100 text-red-900",
  APPLICABLE: "bg-red-100 text-red-900",
};

export function Badge({ value }: { value: string }) {
  return (
    <span
      className={`inline-block rounded px-2 py-0.5 text-xs font-semibold ${
        BADGE_COLORS[value] ?? "bg-neutral-200 text-neutral-800"
      }`}
    >
      {value.replaceAll("_", " ")}
    </span>
  );
}

export function Section({
  title,
  right,
  children,
}: {
  title: string;
  right?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="space-y-3 rounded border border-neutral-200 p-4 dark:border-neutral-800">
      <div className="flex items-center justify-between gap-2">
        <h2 className="font-semibold">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function SourceIds({ ids }: { ids: string[] }) {
  if (!ids.length) return null;
  return (
    <span className="ml-1 inline-flex flex-wrap gap-1">
      {ids.map((id) => (
        <a
          key={id}
          href={`#src-${id}`}
          className="rounded bg-neutral-100 px-1.5 font-mono text-xs text-neutral-600 hover:bg-neutral-200 dark:bg-neutral-800 dark:text-neutral-300"
        >
          {id}
        </a>
      ))}
    </span>
  );
}

export function FindingList({
  title,
  items,
}: {
  title?: string;
  items: ReviewFinding[];
}) {
  if (!items.length) return null;
  return (
    <div className="space-y-1">
      {title && <h3 className="text-sm font-medium">{title}</h3>}
      <ul className="list-disc space-y-1 pl-5 text-sm">
        {items.map((f, i) => (
          <li key={i}>
            {f.summary}
            <span className="ml-1 text-xs text-neutral-500">
              [{f.evidence_kind.toLowerCase().replaceAll("_", " ")}]
            </span>
            <SourceIds ids={f.evidence_source_ids} />
          </li>
        ))}
      </ul>
    </div>
  );
}

export function Botanicals({ items }: { items: BotanicalResult[] }) {
  if (!items.length) return null;
  return (
    <Section title="Ingredients (botanical lookup)">
      <ul className="space-y-2 text-sm">
        {items.map((b, i) => (
          <li key={i} className="space-y-0.5">
            <div className="flex flex-wrap items-center gap-2">
              <EntityLink
                term={b.botanical_name ?? b.input_term}
                label="Herb"
                className="font-medium"
              >
                {b.input_term}
              </EntityLink>
              {b.botanical_name && (
                <em className="text-neutral-600 dark:text-neutral-400">
                  {b.botanical_name}
                </em>
              )}
              <Badge value={b.status} />
              {b.confidence > 0 && (
                <span className="text-xs text-neutral-500">
                  {Math.round(b.confidence * 100)}% confidence
                </span>
              )}
            </div>
            {b.candidates.length > 0 && (
              <div className="text-xs text-neutral-600 dark:text-neutral-400">
                Candidates:{" "}
                {b.candidates.map((c, j) => (
                  <span key={c.botanical_name}>
                    {j > 0 && ", "}
                    <EntityLink term={c.botanical_name} label="Herb" />
                  </span>
                ))}
              </div>
            )}
            {b.notes && (
              <div className="text-xs text-neutral-500">{b.notes}</div>
            )}
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function Verification({ v }: { v: VerificationResult | null }) {
  if (!v) return null;
  return (
    <Section title="Verification" right={<Badge value={v.outcome} />}>
      {v.claims.length > 0 && (
        <ul className="space-y-1 text-sm">
          {v.claims.map((c, i) => (
            <li key={i} className="flex flex-wrap items-start gap-2">
              <Badge value={c.status} />
              <span className="flex-1">
                {c.claim}
                <SourceIds ids={c.evidence_source_ids} />
              </span>
            </li>
          ))}
        </ul>
      )}
      {v.stripped_unsupported_claims.length > 0 && (
        <div className="text-sm">
          <h3 className="font-medium">Removed unsupported claims</h3>
          <ul className="list-disc pl-5 text-neutral-600 line-through dark:text-neutral-400">
            {v.stripped_unsupported_claims.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {v.escalation_reasons.length > 0 && (
        <div className="text-sm">
          <h3 className="font-medium">Escalation reasons</h3>
          <ul className="list-disc pl-5">
            {v.escalation_reasons.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}
      {v.notes && <p className="text-sm text-neutral-500">{v.notes}</p>}
    </Section>
  );
}

export function Sources({
  items,
  terms,
}: {
  items: RetrievedSource[];
  terms?: string[];
}) {
  if (!items.length) return null;
  return (
    <Section
      title={`Sources (${items.length})`}
      right={
        <span className="text-xs text-neutral-500">
          Click an underlined name to open its knowledge graph
        </span>
      }
    >
      <ul className="space-y-2">
        {items.map((s) => (
          <li
            key={s.id}
            id={`src-${s.id}`}
            className="scroll-mt-20 rounded border border-neutral-200 p-2 text-sm target:border-green-600 target:bg-green-50 dark:border-neutral-800 dark:target:bg-green-950"
          >
            <details>
              <summary className="cursor-pointer">
                <span className="font-mono text-xs text-neutral-500">
                  {s.id}
                </span>{" "}
                <span className="font-medium">{s.title}</span>
                {s.section && (
                  <span className="text-neutral-500"> · {s.section}</span>
                )}
                {s.legal_scope && (
                  <span
                    className={`ml-2 rounded px-1.5 py-0.5 text-xs font-medium ${
                      s.legal_scope === "international"
                        ? "bg-sky-100 text-sky-900 dark:bg-sky-900/40 dark:text-sky-100"
                        : "bg-orange-100 text-orange-900 dark:bg-orange-900/40 dark:text-orange-100"
                    }`}
                  >
                    {SCOPE_LABELS[s.legal_scope]}
                  </span>
                )}
                {s.is_fixture && (
                  <span className="ml-2 text-xs text-amber-700">(fixture)</span>
                )}
              </summary>
              <p className="mt-2 whitespace-pre-wrap text-neutral-700 dark:text-neutral-300">
                <LinkifiedText text={s.text} extraTerms={terms} />
              </p>
              <div className="mt-1 text-xs text-neutral-500">
                {s.source_type}
                {s.jurisdiction && ` · ${s.jurisdiction}`}
                {s.effective_date && ` · ${s.effective_date}`} · score{" "}
                {s.retrieval_score.toFixed(3)}
                {s.source_url && (
                  <>
                    {" · "}
                    <a
                      href={s.source_url}
                      target="_blank"
                      rel="noreferrer"
                      className="underline"
                    >
                      link
                    </a>
                  </>
                )}
              </div>
            </details>
          </li>
        ))}
      </ul>
    </Section>
  );
}

export function FinalAnswer({
  answer,
  disclaimer,
  terms,
}: {
  answer: string | null;
  disclaimer: string;
  terms?: string[];
}) {
  return (
    <>
      {answer && (
        <Section title="Summary">
          <p className="whitespace-pre-wrap text-sm leading-relaxed">
            <LinkifiedText text={answer} extraTerms={terms} />
          </p>
        </Section>
      )}
      <p className="text-xs text-neutral-500">{disclaimer}</p>
    </>
  );
}

export function PdfUpload<T extends DocumentExtractResponse>({
  label,
  hint,
  doc,
  extract,
  onChange,
  onError,
  disabled,
  showText = true,
}: {
  label: string;
  hint?: string;
  doc: T | null;
  extract: (file: File) => Promise<T>;
  onChange: (doc: T | null) => void;
  onError: (message: string | null) => void;
  disabled?: boolean;
  showText?: boolean;
}) {
  const [extracting, setExtracting] = useState(false);
  const fileRef = useRef<HTMLInputElement>(null);

  async function onFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    if (!file) return;
    setExtracting(true);
    onError(null);
    try {
      const extracted = await extract(file);
      onChange({ ...extracted, filename: extracted.filename ?? file.name });
    } catch (err) {
      onError(err instanceof Error ? err.message : String(err));
      if (fileRef.current) fileRef.current.value = "";
    } finally {
      setExtracting(false);
    }
  }

  function remove() {
    onChange(null);
    if (fileRef.current) fileRef.current.value = "";
  }

  return (
    <>
      <Field label={label} hint={hint}>
        <input
          ref={fileRef}
          type="file"
          accept="application/pdf"
          disabled={extracting || disabled}
          onChange={onFile}
          className="block w-full text-sm file:mr-3 file:rounded file:border-0 file:bg-green-700 file:px-3 file:py-1.5 file:text-sm file:font-medium file:text-white hover:file:bg-green-800 disabled:opacity-50"
        />
      </Field>
      {extracting && (
        <p className="text-sm text-neutral-500">
          Extracting text (scanned pages may take a while)...
        </p>
      )}
      {doc && !extracting && (
        <DocumentStatus doc={doc} onRemove={remove} showText={showText} />
      )}
    </>
  );
}

export function DocumentStatus({
  doc,
  onRemove,
  showText = true,
}: {
  doc: DocumentExtractResponse;
  onRemove: () => void;
  showText?: boolean;
}) {
  const ocrPages = doc.pages.filter((p) => p.method === "ocr").length;
  return (
    <div className="space-y-2 rounded border border-neutral-200 p-3 text-sm dark:border-neutral-800">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{doc.filename ?? "document.pdf"}</span>
        <span className="text-neutral-500">
          {doc.pages.length} of {doc.total_pages} page
          {doc.total_pages === 1 ? "" : "s"} read
        </span>
        {ocrPages > 0 && (
          <span className="rounded bg-amber-100 px-2 py-0.5 text-xs font-semibold text-amber-900">
            OCR used on {ocrPages} page{ocrPages === 1 ? "" : "s"}
          </span>
        )}
        <button
          type="button"
          onClick={onRemove}
          className="ml-auto text-xs text-neutral-500 hover:text-red-600"
        >
          Remove
        </button>
      </div>
      {doc.truncated && (
        <p className="text-xs text-amber-700">
          Only the first {doc.pages.length} pages were processed.
        </p>
      )}
      {showText && doc.summary && (
        <p className="text-neutral-700 dark:text-neutral-300">{doc.summary}</p>
      )}
      {showText && (
        <details>
          <summary className="cursor-pointer text-xs text-neutral-500">
            Extracted text ({doc.document_text.length.toLocaleString()} chars)
          </summary>
          <pre className="mt-2 max-h-64 overflow-auto whitespace-pre-wrap text-xs text-neutral-600 dark:text-neutral-400">
            {doc.document_text}
          </pre>
        </details>
      )}
    </div>
  );
}
