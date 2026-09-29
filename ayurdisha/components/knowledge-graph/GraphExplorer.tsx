"use client";

import dynamic from "next/dynamic";
import { useEffect, useMemo, useState } from "react";
import { api } from "@/lib/api";
import type { KgGraph, KgNode, KgPropValue } from "@/lib/types";
import { LABELS, labelColor } from "./labels";

const GraphCanvas = dynamic(() => import("./GraphCanvas"), {
  ssr: false,
  loading: () => <CanvasMessage text="Loading graph…" />,
});

const HIDDEN_PROPS = new Set(["origin", "snippet", "url", "source_id", "ident"]);

function CanvasMessage({ text }: { text: string }) {
  return (
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-neutral-500">
      {text}
    </div>
  );
}

function LabelDot({ label }: { label: string }) {
  return (
    <span
      className="inline-block h-2.5 w-2.5 shrink-0 rounded-full"
      style={{ backgroundColor: labelColor(label) }}
    />
  );
}

function formatValue(v: KgPropValue): string {
  if (Array.isArray(v)) return v.join(", ");
  if (typeof v === "number") return Number.isInteger(v) ? String(v) : v.toFixed(2);
  return String(v);
}

function relationText(type: string, outgoing: boolean) {
  const t = type.replaceAll("_", " ").toLowerCase();
  return outgoing ? t : `← ${t}`;
}

export function GraphExplorer({ query }: { query: string }) {
  const [history, setHistory] = useState<string[]>([query]);
  const [depth, setDepth] = useState(1);
  const [result, setResult] = useState<{
    key: string;
    graph: KgGraph | null;
    error: string | null;
  } | null>(null);
  const [selectedKey, setSelectedKey] = useState<string | null>(null);
  const current = history[history.length - 1];
  const requestKey = `${current}\n${depth}`;

  useEffect(() => {
    let cancelled = false;
    api
      .kgEntity(current, depth)
      .then((g) => {
        if (cancelled) return;
        setResult({ key: requestKey, graph: g, error: null });
        setSelectedKey(g.center);
      })
      .catch((e: unknown) => {
        if (cancelled) return;
        const message = e instanceof Error ? e.message : String(e);
        setResult({ key: requestKey, graph: null, error: message });
      });
    return () => {
      cancelled = true;
    };
  }, [current, depth, requestKey]);

  const loading = result?.key !== requestKey;
  const graph = result?.graph ?? null;
  const error = loading ? null : (result?.error ?? null);

  const byKey = useMemo(
    () => new Map((graph?.nodes ?? []).map((n) => [n.key, n])),
    [graph],
  );
  const selected = (selectedKey && byKey.get(selectedKey)) || null;
  const center = (graph?.center && byKey.get(graph.center)) || null;
  const presentLabels = useMemo(
    () => [...new Set((graph?.nodes ?? []).map((n) => n.label))],
    [graph],
  );

  const connections = useMemo(() => {
    if (!graph || !selected) return [];
    return graph.edges
      .filter((e) => e.source === selected.key || e.target === selected.key)
      .map((e) => {
        const outgoing = e.source === selected.key;
        const other = byKey.get(outgoing ? e.target : e.source);
        return other ? { edge: e, other, outgoing } : null;
      })
      .filter((c) => c !== null)
      .sort((a, b) => a.other.label.localeCompare(b.other.label));
  }, [graph, selected, byKey]);

  const explore = (node: KgNode) => {
    if (node.key !== graph?.center) setHistory((h) => [...h, node.key]);
  };

  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="flex flex-wrap items-center gap-2 border-b border-neutral-200 px-4 py-2 text-sm dark:border-neutral-800">
        {history.length > 1 && (
          <button
            type="button"
            onClick={() => setHistory((h) => h.slice(0, -1))}
            className="rounded px-2 py-1 text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            ← Back
          </button>
        )}
        {center && (
          <span className="flex items-center gap-2 font-medium">
            <LabelDot label={center.label} />
            {center.name}
            <span className="text-xs font-normal text-neutral-500">
              {LABELS[center.label]?.title ?? center.label}
            </span>
          </span>
        )}
        <div className="ml-auto flex items-center gap-2">
          <span className="text-xs text-neutral-500">Hops</span>
          <div className="inline-flex rounded border border-neutral-300 p-0.5 dark:border-neutral-700">
            {[1, 2].map((d) => (
              <button
                key={d}
                type="button"
                onClick={() => setDepth(d)}
                className={`rounded px-2.5 py-0.5 text-xs font-medium ${
                  depth === d
                    ? "bg-green-700 text-white"
                    : "text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
                }`}
              >
                {d}
              </button>
            ))}
          </div>
        </div>
      </div>

      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        <div className="relative min-h-[320px] flex-1 bg-neutral-50 dark:bg-neutral-950">
          {error ? (
            <CanvasMessage text={error} />
          ) : graph ? (
            <GraphCanvas
              graph={graph}
              selectedKey={selectedKey}
              onSelect={(n) => setSelectedKey(n?.key ?? graph.center)}
            />
          ) : (
            <CanvasMessage text="Loading graph…" />
          )}
          {loading && graph && (
            <span className="absolute left-3 top-3 rounded bg-white/80 px-2 py-0.5 text-xs text-neutral-500 dark:bg-neutral-900/80">
              Loading…
            </span>
          )}
          {graph?.truncated && (
            <span className="absolute right-3 top-3 rounded bg-amber-100 px-2 py-0.5 text-xs text-amber-900">
              Showing first {graph.nodes.length} nodes
            </span>
          )}
          {presentLabels.length > 0 && (
            <div className="absolute bottom-2 left-2 flex max-w-[95%] flex-wrap gap-x-3 gap-y-1 rounded bg-white/85 px-2 py-1 text-xs text-neutral-600 dark:bg-neutral-900/85 dark:text-neutral-300">
              {presentLabels.map((l) => (
                <span key={l} className="flex items-center gap-1">
                  <LabelDot label={l} />
                  {LABELS[l]?.title ?? l}
                </span>
              ))}
            </div>
          )}
        </div>

        {selected && (
          <aside className="max-h-[40vh] w-full shrink-0 space-y-3 overflow-y-auto border-t border-neutral-200 p-4 text-sm md:max-h-none md:w-80 md:border-l md:border-t-0 dark:border-neutral-800">
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-neutral-500">
                <LabelDot label={selected.label} />
                {LABELS[selected.label]?.title ?? selected.label}
              </div>
              <h3 className="font-semibold leading-snug">{selected.name}</h3>
              {selected.aliases.length > 0 && (
                <p className="text-xs text-neutral-500">
                  Also: {selected.aliases.filter((a) => a !== selected.name).join(", ")}
                </p>
              )}
            </div>

            {selected.key !== graph?.center && (
              <button
                type="button"
                onClick={() => explore(selected)}
                className="rounded bg-green-700 px-3 py-1 text-xs font-medium text-white hover:bg-green-800"
              >
                Explore from here
              </button>
            )}

            {typeof selected.props.snippet === "string" && (
              <p className="whitespace-pre-wrap rounded bg-neutral-100 p-2 text-xs text-neutral-700 dark:bg-neutral-900 dark:text-neutral-300">
                {selected.props.snippet}
              </p>
            )}

            <dl className="space-y-1 text-xs">
              {Object.entries(selected.props)
                .filter(([k, v]) => !HIDDEN_PROPS.has(k) && v !== null && v !== "")
                .map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="w-28 shrink-0 capitalize text-neutral-500">
                      {k.replaceAll("_", " ")}
                    </dt>
                    <dd className="min-w-0 break-words">{formatValue(v)}</dd>
                  </div>
                ))}
              {typeof selected.props.origin === "string" && (
                <div className="flex gap-2">
                  <dt className="w-28 shrink-0 text-neutral-500">Provenance</dt>
                  <dd>{selected.props.origin}</dd>
                </div>
              )}
            </dl>

            {typeof selected.props.url === "string" && (
              <a
                href={selected.props.url}
                target="_blank"
                rel="noreferrer"
                className="block text-xs text-green-700 underline dark:text-green-400"
              >
                Open source ↗
              </a>
            )}

            {connections.length > 0 && (
              <div className="space-y-1">
                <h4 className="text-xs font-medium uppercase tracking-wide text-neutral-500">
                  Connections ({connections.length})
                </h4>
                <ul className="space-y-0.5">
                  {connections.map(({ edge, other, outgoing }) => (
                    <li key={`${edge.source}-${edge.type}-${edge.target}`}>
                      <button
                        type="button"
                        onClick={() => setSelectedKey(other.key)}
                        className="flex w-full items-center gap-2 rounded px-1 py-0.5 text-left text-xs hover:bg-neutral-100 dark:hover:bg-neutral-800"
                      >
                        <LabelDot label={other.label} />
                        <span className="min-w-0 flex-1 truncate">{other.name}</span>
                        <span className="shrink-0 text-neutral-400">
                          {relationText(edge.type, outgoing)}
                        </span>
                      </button>
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </aside>
        )}
      </div>
    </div>
  );
}
