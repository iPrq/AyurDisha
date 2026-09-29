"use client";

import { useState } from "react";
import { formulationApi } from "@/lib/formulation/api";
import type { FormulationContext, VersionComparison, VersionInfo } from "@/lib/formulation/types";

export function VersionBar({
  ctx,
  versions,
  external,
}: {
  ctx: FormulationContext;
  versions: VersionInfo[];
  external: VersionComparison | null;
}) {
  const [comparison, setComparison] = useState<VersionComparison | null>(null);
  const [error, setError] = useState<string | null>(null);
  const current = versions.find((v) => v.version === ctx.version);
  const previous = versions.filter((v) => v.version < ctx.version).at(-1);
  const shown = comparison ?? external;

  async function compare() {
    setError(null);
    try {
      setComparison(await formulationApi.compare(ctx.formulation_id));
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    }
  }

  return (
    <div className="space-y-1 text-xs text-neutral-600 dark:text-neutral-400">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-1">
        <span className="rounded bg-neutral-100 px-1.5 py-0.5 font-mono dark:bg-neutral-800">v{ctx.version}</span>
        {current && <span>Current: {current.change_summary}</span>}
        {previous && (
          <span className="text-neutral-400">
            Previous v{previous.version}: {previous.change_summary}
          </span>
        )}
        {previous && (
          <button type="button" onClick={compare} className="underline">
            What changed?
          </button>
        )}
      </div>
      {error && <p className="text-red-700">{error}</p>}
      {shown && (
        <div className="rounded bg-neutral-100 p-2 dark:bg-neutral-900">
          <div className="font-medium">
            v{shown.from_version} → v{shown.to_version}
          </div>
          {shown.changes.length ? (
            <ul className="list-disc pl-4">
              {shown.changes.map((c, i) => (
                <li key={i}>{c}</li>
              ))}
            </ul>
          ) : (
            <p>No differences.</p>
          )}
        </div>
      )}
    </div>
  );
}
