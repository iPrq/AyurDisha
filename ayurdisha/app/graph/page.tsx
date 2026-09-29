"use client";

import { useEffect, useState } from "react";
import { GraphExplorer } from "@/components/knowledge-graph/GraphExplorer";
import { labelColor, LABELS } from "@/components/knowledge-graph/labels";
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
    <div className="space-y-4">
      <div className="space-y-1">
        <h1 className="text-2xl font-semibold">Knowledge graph</h1>
        <p className="text-sm text-neutral-600 dark:text-neutral-400">
          Herbs, compounds, classical formulations, patents and the sources behind
          every analysis, stored in Neo4j. Click a node for details and use
          &quot;Explore from here&quot; to move through the graph.
        </p>
      </div>

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
          <ul className="absolute z-10 mt-1 w-full overflow-hidden rounded border border-neutral-200 bg-white text-sm shadow dark:border-neutral-700 dark:bg-neutral-900">
            {suggestions.map((s) => (
              <li key={s.key}>
                <button
                  type="button"
                  onClick={() => choose(s.key)}
                  className="flex w-full items-center gap-2 px-3 py-1.5 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
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
            className="rounded bg-green-100 px-2 py-0.5 text-green-900 hover:bg-green-200 dark:bg-green-900/40 dark:text-green-100"
          >
            {ex}
          </button>
        ))}
      </div>

      <div className="h-[70vh] overflow-hidden rounded border border-neutral-200 dark:border-neutral-800">
        <GraphExplorer key={query} query={query} />
      </div>
    </div>
  );
}
