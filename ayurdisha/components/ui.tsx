"use client";

import { useRef, useState } from "react";
import {
  EntityLink,
  LinkifiedText,
} from "@/components/knowledge-graph/KnowledgeGraphProvider";
import { Dishu } from "@/components/mascot/Dishu";
import type {
  BotanicalResult,
  DocumentExtractResponse,
  LegalScope,
  RetrievedSource,
  ReviewFinding,
  VerificationResult,
} from "@/lib/types";

export const inputClass =
  "w-full rounded-xl border border-line bg-surface px-4 py-2.5 text-sm text-ink placeholder:text-neutral-400 transition-shadow focus:border-leaf-bright focus:outline-none focus:ring-4 focus:ring-leaf-bright/15";

/** Card wrapper for tool forms. */
export const formCardClass =
  "space-y-5 rounded-[2rem] border border-line bg-surface p-6 shadow-soft sm:p-8";

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
    <label className="block space-y-1.5">
      <span className="text-sm font-semibold">{label}</span>
      {children}
      {hint && <span className="block text-xs text-muted">{hint}</span>}
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
              className="flex items-center gap-1 rounded-full bg-blob px-3 py-1 text-sm font-medium text-leaf"
            >
              {v}
              <button
                type="button"
                className="text-leaf hover:text-clay"
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

/**
 * Indian / international sources. `value`/`onChange` come from
 * `useSourceScope`, so the choice is shared by every tool page.
 */
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
    <div className="space-y-1.5">
      <span className="block text-sm font-semibold">Sources</span>
      <div
        role="radiogroup"
        aria-label="Sources"
        className="inline-flex rounded-full border border-line bg-mint p-1"
      >
        {(Object.keys(SCOPE_LABELS) as LegalScope[]).map((scope) => (
          <button
            key={scope}
            type="button"
            role="radio"
            aria-checked={value === scope}
            onClick={() => onChange(scope)}
            className={`rounded-full px-5 py-1.5 text-sm font-semibold transition-colors ${
              value === scope
                ? "bg-leaf text-canvas shadow-soft"
                : "text-muted hover:text-ink"
            }`}
          >
            {SCOPE_LABELS[scope]}
          </button>
        ))}
      </div>
      <span className="block text-xs text-muted">
        {descriptions[value]} Your choice carries over to the other tools.
      </span>
    </div>
  );
}

export function SubmitButton({ loading }: { loading: boolean }) {
  return (
    <button
      type="submit"
      disabled={loading}
      className="inline-flex items-center gap-2 rounded-full bg-turmeric px-7 py-3 text-sm font-semibold text-[#14261C] shadow-soft transition-transform hover:-translate-y-0.5 hover:bg-turmeric-deep disabled:translate-y-0 disabled:opacity-60"
    >
      {loading && (
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-[#14261C]/30 border-t-[#14261C]" />
      )}
      {loading ? "Analysing..." : "Run analysis"}
    </button>
  );
}

export function ErrorBanner({ message }: { message: string }) {
  const offline = /unreachable|failed to fetch|502/i.test(message);
  return (
    <div
      role="alert"
      className="flex items-center gap-4 rounded-3xl border border-clay/40 bg-clay/10 p-4 text-sm"
    >
      <Dishu pose={offline ? "sleep" : "shrug"} size={72} className="shrink-0" />
      <div className="space-y-1">
        <p className="font-display font-bold">
          {offline ? "The backend is taking a nap" : "Something went wrong"}
        </p>
        <p className="text-muted">{message}</p>
        {offline && (
          <p className="text-xs text-muted">
            Start the API from <code className="font-mono">app/</code> with{" "}
            <code className="font-mono">uv run uvicorn main:app --reload</code>.
          </p>
        )}
      </div>
    </div>
  );
}

const TONE = {
  good: "bg-[#DDF1E2] text-[#1E6B43] dark:bg-leaf/15 dark:text-leaf",
  warn: "bg-[#FDEBD0] text-[#8A520A] dark:bg-turmeric/15 dark:text-turmeric",
  bad: "bg-[#FBE1D6] text-[#A5401A] dark:bg-clay/20 dark:text-[#F4A585]",
  review: "bg-[#DCE8FF] text-[#2F5BC0] dark:bg-sky/15 dark:text-sky",
};

const BADGE_COLORS: Record<string, string> = {
  FAVORABLE: TONE.good,
  PASS: TONE.good,
  RESOLVED: TONE.good,
  SUPPORTED: TONE.good,
  NOT_APPLICABLE: TONE.good,
  MODERATE: TONE.warn,
  AMBIGUOUS: TONE.warn,
  PARTIALLY_SUPPORTED: TONE.warn,
  UNCERTAIN: TONE.warn,
  EVIDENCE_GAP: TONE.warn,
  HUMAN_REVIEW_REQUIRED: TONE.review,
  CHALLENGING: TONE.bad,
  FAIL: TONE.bad,
  UNSUPPORTED: TONE.bad,
  APPLICABLE: TONE.bad,
  TRIGGERED: TONE.bad,
};

export function Badge({ value }: { value: string }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-semibold ${
        BADGE_COLORS[value] ?? "bg-mint text-muted"
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
    <section className="result-section space-y-4 rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <h2 className="font-display text-lg font-bold">{title}</h2>
        {right}
      </div>
      {children}
    </section>
  );
}

export function SubHeading({
  children,
  count,
}: {
  children: React.ReactNode;
  count?: number;
}) {
  return (
    <h3 className="flex items-center gap-2 text-xs font-bold uppercase tracking-wider text-leaf">
      {children}
      {count !== undefined && (
        <span className="rounded-full bg-mint px-2 py-0.5 text-[11px] font-semibold text-muted">
          {count}
        </span>
      )}
    </h3>
  );
}

/** Headed list that shows the first `limit` items and hides the rest behind a toggle. */
export function PreviewList<T>({
  title,
  items,
  limit = 3,
  render,
  variant = "bullets",
}: {
  title: string;
  items: T[];
  limit?: number;
  render: (item: T, index: number) => React.ReactNode;
  variant?: "bullets" | "cards" | "chips";
}) {
  const [open, setOpen] = useState(false);
  if (!items.length) return null;
  const shown = open ? items : items.slice(0, limit);
  const hidden = items.length - limit;
  const listClass = {
    bullets: "list-disc space-y-1.5 pl-5 text-sm leading-relaxed",
    cards: "grid gap-2 sm:grid-cols-2",
    chips: "flex flex-wrap gap-2",
  }[variant];
  const itemClass = {
    bullets: "",
    cards: "rounded-2xl border border-line bg-mint/40 p-3 text-sm",
    chips: "rounded-full border border-line bg-mint/60 px-3 py-1 text-sm",
  }[variant];
  return (
    <div className="space-y-2">
      <SubHeading count={items.length}>{title}</SubHeading>
      <ul className={listClass}>
        {shown.map((item, i) => (
          <li key={i} className={itemClass}>
            {render(item, i)}
          </li>
        ))}
      </ul>
      {hidden > 0 && (
        <button
          type="button"
          onClick={() => setOpen((o) => !o)}
          aria-expanded={open}
          className="text-sm font-medium text-leaf hover:underline"
        >
          {open ? "Show less" : `Show ${hidden} more`}
        </button>
      )}
    </div>
  );
}

/** Secondary detail collapsed behind a toggle. */
export function MoreDetails({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <details className="group rounded-2xl border border-line/70 px-4 py-3">
      <summary className="flex cursor-pointer list-none items-center justify-between text-sm font-medium text-leaf">
        {label}
        <span className="text-muted transition-transform group-open:rotate-180">▾</span>
      </summary>
      <div className="mt-3 space-y-3">{children}</div>
    </details>
  );
}

export function CollapsibleSources({
  items,
  terms,
}: {
  items: RetrievedSource[];
  terms?: string[];
}) {
  if (!items.length) return null;
  return (
    <details className="group rounded-3xl border border-line bg-surface p-5 shadow-soft sm:p-6">
      <summary className="flex cursor-pointer list-none items-center justify-between">
        <h2 className="font-display text-lg font-bold">Sources ({items.length})</h2>
        <span className="text-sm font-medium text-leaf">
          <span className="group-open:hidden">Show</span>
          <span className="hidden group-open:inline">Hide</span>
        </span>
      </summary>
      <div className="mt-4">
        <SourceList items={items} terms={terms} />
      </div>
    </details>
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
          className="rounded-md bg-mint px-1.5 font-mono text-xs text-muted hover:bg-blob hover:text-leaf"
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
      <SourceList items={items} terms={terms} />
    </Section>
  );
}

function SourceList({
  items,
  terms,
}: {
  items: RetrievedSource[];
  terms?: string[];
}) {
  return (
      <ul className="space-y-2">
        {items.map((s) => (
          <li
            key={s.id}
            id={`src-${s.id}`}
            className="scroll-mt-24 rounded-xl border border-line p-3 text-sm target:border-leaf-bright target:bg-mint"
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
          className="block w-full cursor-pointer rounded-2xl border-2 border-dashed border-line bg-mint/60 p-3 text-sm text-muted transition-colors file:mr-4 file:cursor-pointer file:rounded-full file:border-0 file:bg-leaf file:px-4 file:py-2 file:text-sm file:font-semibold file:text-canvas hover:border-leaf-bright disabled:opacity-50"
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
    <div className="space-y-2 rounded-2xl border border-line bg-mint/60 p-4 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">{doc.filename ?? "document.pdf"}</span>
        <span className="text-neutral-500">
          {doc.pages.length} of {doc.total_pages} page
          {doc.total_pages === 1 ? "" : "s"} read
        </span>
        {ocrPages > 0 && (
          <span className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${TONE.warn}`}>
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
