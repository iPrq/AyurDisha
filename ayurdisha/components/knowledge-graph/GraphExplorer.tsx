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
    <div className="flex h-full items-center justify-center p-6 text-center text-sm text-muted">
      {text}
    </div>
  );
}

function LabelDot({ label }: { label: string }) {
  return (
    <span
      className="inline-block h-2 w-2 shrink-0 rounded-full"
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
      {/* ── TOOLBAR ────────────────────────────────── */}
      <div className="flex flex-wrap items-center gap-2 border-b border-line px-4 py-2 text-sm">
        {history.length > 1 && (
          <button
            type="button"
            onClick={() => setHistory((h) => h.slice(0, -1))}
            className="rounded px-2 py-1 text-muted hover:bg-mint hover:text-ink transition-colors"
          >
            ← Back
          </button>
        )}

        {center && (
          <span className="flex items-center gap-2 font-medium">
            <LabelDot label={center.label} />
            {center.name}
            <span className="text-xs text-muted">
              {LABELS[center.label]?.title ?? center.label}
            </span>
          </span>
        )}

        <div className="ml-auto flex items-center gap-3">
          {/* Stats */}
          {graph && (
            <span className="hidden sm:inline text-xs text-muted tabular-nums">
              {graph.nodes.length} nodes · {graph.edges.length} edges
            </span>
          )}

          {/* Hops */}
          <div className="flex items-center gap-1.5">
            <span className="text-xs text-muted">Depth</span>
            <div className="inline-flex rounded-md border border-line p-0.5">
              {[1, 2].map((d) => (
                <button
                  key={d}
                  type="button"
                  onClick={() => setDepth(d)}
                  className={`rounded px-2.5 py-0.5 text-xs font-medium transition-colors ${
                    depth === d
                      ? "bg-leaf text-white"
                      : "text-muted hover:bg-mint hover:text-ink"
                  }`}
                >
                  {d}
                </button>
              ))}
            </div>
          </div>
        </div>
      </div>

      {/* ── MAIN ───────────────────────────────────── */}
      <div className="flex min-h-0 flex-1 flex-col md:flex-row">
        {/* Canvas */}
        <div className="relative min-h-[320px] flex-1 bg-neutral-50">
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
            <span className="absolute left-3 top-3 rounded bg-white/80 px-2 py-0.5 text-xs text-muted">
              Loading…
            </span>
          )}

          {graph?.truncated && (
            <span className="absolute right-3 top-3 rounded bg-amber-50 border border-amber-200 px-2 py-0.5 text-xs text-amber-800">
              Showing first {graph.nodes.length} nodes
            </span>
          )}

          {/* Legend */}
          {presentLabels.length > 0 && (
            <div className="absolute bottom-2 left-2 flex max-w-[95%] flex-wrap gap-x-3 gap-y-1 rounded-lg bg-white/90 px-2.5 py-1.5 text-[11px] text-muted border border-line/50">
              {presentLabels.map((l) => (
                <span key={l} className="flex items-center gap-1.5">
                  <LabelDot label={l} />
                  {LABELS[l]?.title ?? l}
                </span>
              ))}
            </div>
          )}
        </div>

        {/* ── SIDEBAR ──────────────────────────────── */}
        {selected && (
          <aside className="max-h-[40vh] w-full shrink-0 space-y-4 overflow-y-auto border-t border-line p-4 text-sm md:max-h-none md:w-80 md:border-l md:border-t-0">
            {/* Mobile drag handle */}
            <div className="mx-auto h-1 w-10 rounded-full bg-line md:hidden" />

            {/* Header */}
            <div className="space-y-1">
              <div className="flex items-center gap-2 text-xs uppercase tracking-wide text-muted">
                <LabelDot label={selected.label} />
                {LABELS[selected.label]?.title ?? selected.label}
              </div>
              <h3 className="text-lg font-semibold leading-snug">{selected.name}</h3>
              {selected.aliases.length > 0 && (
                <p className="text-xs text-muted">
                  Also: {selected.aliases.filter((a) => a !== selected.name).join(", ")}
                </p>
              )}
            </div>

            {/* Action */}
            {selected.key !== graph?.center && (
              <button
                type="button"
                onClick={() => explore(selected)}
                className="rounded-lg bg-leaf px-3 py-1.5 text-xs font-medium text-white hover:bg-green-800 transition-colors"
              >
                Explore from here
              </button>
            )}

            {/* Snippet */}
            {typeof selected.props.snippet === "string" && (
              <p className="whitespace-pre-wrap rounded-lg bg-mint/40 p-3 text-xs leading-relaxed text-ink/80">
                {selected.props.snippet}
              </p>
            )}

            {/* Properties */}
            <dl className="space-y-1.5 text-xs">
              {Object.entries(selected.props)
                .filter(([k, v]) => !HIDDEN_PROPS.has(k) && v !== null && v !== "")
                .map(([k, v]) => (
                  <div key={k} className="flex gap-2">
                    <dt className="w-28 shrink-0 capitalize text-muted">
                      {k.replaceAll("_", " ")}
                    </dt>
                    <dd className="min-w-0 break-words">{formatValue(v)}</dd>
                  </div>
                ))}
              {typeof selected.props.origin === "string" && (
                <div className="flex gap-2">
                  <dt className="w-28 shrink-0 text-muted">Provenance</dt>
                  <dd>{selected.props.origin}</dd>
                </div>
              )}
            </dl>

            {typeof selected.props.url === "string" && (
              <a
                href={selected.props.url}
                target="_blank"
                rel="noreferrer"
                className="inline-block text-xs text-leaf underline underline-offset-2 hover:text-green-800 transition-colors"
              >
                Open source ↗
              </a>
            )}

            {/* Connections */}
            {connections.length > 0 && (
              <div className="space-y-1.5">
                <h4 className="text-xs font-medium uppercase tracking-wide text-muted">
                  Connections ({connections.length})
                </h4>
                <ul className="space-y-0.5">
                  {connections.map(({ edge, other, outgoing }) => (
                    <li key={`${edge.source}-${edge.type}-${edge.target}`}>
                      <button
                        type="button"
                        onClick={() => setSelectedKey(other.key)}
                        className="flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left text-xs hover:bg-mint transition-colors"
                      >
                        <LabelDot label={other.label} />
                        <span className="min-w-0 flex-1 truncate">{other.name}</span>
                        <span className="shrink-0 text-muted">
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
