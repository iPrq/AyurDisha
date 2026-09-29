"use client";

import { useEffect, useState } from "react";
import { GraphExplorer } from "@/components/knowledge-graph/GraphExplorer";
import { labelColor, LABELS } from "@/components/knowledge-graph/labels";
import { PageHero } from "@/components/tool/PageHero";
import { inputClass } from "@/components/ui";
import { api } from "@/lib/api";
import type { KgNode } from "@/lib/types";

const EXAMPLES = ["Ashwagandha", "Triphala", "Turmeric", "Guggulu", "ginseng"];

export default function GraphPage() {
  const [query, setQuery] = useState("Ashwagandha");
  const [draft, setDraft] = useState("");
  const [suggestions, setSuggestions] = useState<KgNode[]>([]);

  useEffect(() => {
    const q = draft.trim();
    if (q.length < 2) return;
    let cancelled = false;
    const t = setTimeout(() => {
      api
        .kgSearch(q)
        .then((r) => !cancelled && setSuggestions(r.slice(0, 8)))
        .catch(() => !cancelled && setSuggestions([]));
    }, 200);
    return () => {
      cancelled = true;
      clearTimeout(t);
    };
  }, [draft]);

  const choose = (q: string) => {
    setQuery(q);
    setDraft("");
    setSuggestions([]);
  };

  return (
    <div className="space-y-6">
      <PageHero
        eyebrow="Knowledge Graph"
        title="See how every herb connects"
        desc="Herbs, compounds, classical formulations, patents and the sources behind every analysis, stored in Neo4j. Click a node for details and use “Explore from here” to move through the graph."
        pose="connect"
        assistant={false}
      />

      <form
        className="relative"
        onSubmit={(e) => {
          e.preventDefault();
          if (draft.trim()) choose(draft.trim());
        }}
      >
        <input
          className={inputClass}
          value={draft}
          placeholder="Search a herb, formulation, compound or product…"
          onChange={(e) => {
            setDraft(e.target.value);
            if (e.target.value.trim().length < 2) setSuggestions([]);
          }}
        />
        {suggestions.length > 0 && (
          <ul className="absolute z-10 mt-2 w-full overflow-hidden rounded-2xl border border-line bg-surface text-sm shadow-soft">
            {suggestions.map((s) => (
              <li key={s.key}>
                <button
                  type="button"
                  onClick={() => choose(s.key)}
                  className="flex w-full items-center gap-2 px-4 py-2 text-left hover:bg-mint"
                >
                  <span
                    className="h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: labelColor(s.label) }}
                  />
                  <span className="flex-1 truncate">{s.name}</span>
                  <span className="text-xs text-neutral-500">
                    {LABELS[s.label]?.title ?? s.label}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </form>

      <div className="flex flex-wrap gap-2 text-xs">
        {EXAMPLES.map((ex) => (
          <button
            key={ex}
            type="button"
            onClick={() => choose(ex)}
            className="rounded-full bg-blob px-3 py-1 font-medium text-leaf transition-colors hover:bg-leaf hover:text-canvas"
          >
            {ex}
          </button>
        ))}
      </div>

      <div className="h-[70vh] overflow-hidden rounded-[2rem] border border-line bg-surface shadow-soft">
        <GraphExplorer key={query} query={query} />
      </div>
    </div>
  );
}
