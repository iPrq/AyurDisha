"use client";

import {
  createContext,
  Fragment,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
} from "react";
import { api } from "@/lib/api";
import type { BotanicalResult } from "@/lib/types";
import { GraphExplorer } from "./GraphExplorer";
import { labelColor } from "./labels";

interface KgContextValue {
  open: (term: string) => void;
  terms: Map<string, string>;
}

const KgContext = createContext<KgContextValue | null>(null);

const MIN_TERM_LENGTH = 3;

function escapeRegExp(s: string) {
  return s.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
}

export function KnowledgeGraphProvider({ children }: { children: React.ReactNode }) {
  const [query, setQuery] = useState<string | null>(null);
  const [terms, setTerms] = useState<Map<string, string>>(new Map());

  useEffect(() => {
    api
      .kgVocabulary()
      .then((vocab) => {
        const map = new Map<string, string>();
        for (const t of vocab) {
          if (t.term.length >= MIN_TERM_LENGTH) map.set(t.term.toLowerCase(), t.label);
        }
        setTerms(map);
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    if (!query) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setQuery(null);
    window.addEventListener("keydown", onKey);
    const overflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      window.removeEventListener("keydown", onKey);
      document.body.style.overflow = overflow;
    };
  }, [query]);

  const open = useCallback((term: string) => setQuery(term.trim()), []);
  const value = useMemo(() => ({ open, terms }), [open, terms]);

  return (
    <KgContext.Provider value={value}>
      {children}
      {query && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm p-2 sm:p-6"
          onClick={() => setQuery(null)}
        >
          <div
            role="dialog"
            aria-modal="true"
            aria-label={`Knowledge graph: ${query}`}
            className="flex h-[88vh] w-full max-w-6xl flex-col overflow-hidden rounded-xl bg-surface shadow-2xl border border-line"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-line px-4 py-2">
              <h2 className="text-sm font-semibold">Knowledge graph</h2>
              <button
                type="button"
                onClick={() => setQuery(null)}
                className="rounded px-2 text-lg leading-none text-muted hover:bg-mint hover:text-ink transition-colors"
                aria-label="Close"
              >
                ×
              </button>
            </div>
            <div className="min-h-0 flex-1">
              <GraphExplorer key={query} query={query} />
            </div>
          </div>
        </div>
      )}
    </KgContext.Provider>
  );
}

export function useKnowledgeGraph() {
  return useContext(KgContext);
}

export function EntityLink({
  term,
  label,
  children,
  className = "",
}: {
  term: string;
  label?: string;
  children?: React.ReactNode;
  className?: string;
}) {
  const kg = useKnowledgeGraph();
  if (!kg) return <>{children ?? term}</>;
  const entityLabel = label ?? kg.terms.get(term.toLowerCase()) ?? "Herb";
  const color = labelColor(entityLabel);
  return (
    <span className="group relative">
      <button
        type="button"
        title={`Show "${term}" in the knowledge graph`}
        onClick={(e) => {
          e.preventDefault();
          e.stopPropagation();
          kg.open(term);
        }}
        className={`cursor-pointer underline decoration-dotted decoration-2 underline-offset-2 hover:decoration-solid hover:opacity-80 transition-opacity ${className}`}
        style={{ textDecorationColor: color }}
      >
        {children ?? term}
      </button>
      <span className="pointer-events-none absolute bottom-full left-1/2 mb-1 -translate-x-1/2 whitespace-nowrap rounded-md bg-ink/90 px-2 py-1 text-xs text-surface opacity-0 transition-opacity group-hover:opacity-100 z-10 shadow-lg">
        {entityLabel}
      </span>
    </span>
  );
}

/** Renders text with every known herb / formulation / compound name clickable. */
export function LinkifiedText({
  text,
  extraTerms = [],
}: {
  text: string;
  extraTerms?: string[];
}) {
  const kg = useKnowledgeGraph();
  const extraKey = extraTerms.join("\n");
  const pattern = useMemo(() => {
    const all = new Set<string>(kg ? kg.terms.keys() : []);
    for (const t of extraKey.split("\n")) {
      if (t.trim().length >= MIN_TERM_LENGTH) all.add(t.trim().toLowerCase());
    }
    if (!all.size) return null;
    const body = [...all]
      .sort((a, b) => b.length - a.length)
      .map(escapeRegExp)
      .join("|");
    return new RegExp(`(?<![\\w-])(${body})(?![\\w-])`, "gi");
  }, [kg, extraKey]);

  if (!kg || !pattern || !text) return <>{text}</>;
  const parts = text.split(pattern);
  return (
    <>
      {parts.map((part, i) =>
        i % 2 === 1 ? (
          <EntityLink key={i} term={part} />
        ) : (
          <Fragment key={i}>{part}</Fragment>
        ),
      )}
    </>
  );
}

/** Names a response resolved for its ingredients (so they link even before the graph knows them). */
export function botanicalTerms(items: (BotanicalResult | null | undefined)[]): string[] {
  const out = new Set<string>();
  for (const b of items) {
    if (!b) continue;
    [b.input_term, b.botanical_name, ...b.synonyms, ...b.phytochemicals].forEach(
      (t) => t && out.add(t),
    );
  }
  return [...out];
}
