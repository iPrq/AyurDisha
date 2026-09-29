"use client";

import { useEffect, useState } from "react";
import { Dishu } from "@/components/mascot/Dishu";

const STAGES = [
  "Parsing your input",
  "Normalising botanical names",
  "Retrieving statutes and evidence",
  "Scoring and drafting findings",
  "Verifying every claim against sources",
];

/**
 * Shown while an analysis request is in flight. The stage labels rotate on a
 * timer to show what the pipeline does; they are not live progress.
 */
export function LoadingPanel() {
  const [elapsed, setElapsed] = useState(0);

  useEffect(() => {
    const id = setInterval(() => setElapsed((s) => s + 1), 1000);
    return () => clearInterval(id);
  }, []);

  const stage = Math.min(Math.floor(elapsed / 6), STAGES.length - 1);

  return (
    <div
      role="status"
      aria-live="polite"
      className="flex flex-col items-center gap-6 rounded-[2rem] border border-line bg-surface p-8 text-center shadow-soft sm:flex-row sm:text-left"
    >
      <Dishu pose="think" size={120} className="shrink-0" />
      <div className="w-full space-y-3">
        <p className="font-display text-lg font-bold">
          Dishu is reading the sources...
        </p>
        <ol className="space-y-1.5 text-sm">
          {STAGES.map((s, i) => (
            <li
              key={s}
              className={`flex items-center gap-2 transition-colors ${
                i < stage ? "text-leaf" : i === stage ? "font-semibold text-ink" : "text-neutral-400"
              }`}
            >
              <span
                className={`grid h-5 w-5 place-items-center rounded-full text-[10px] ${
                  i < stage
                    ? "bg-leaf-bright text-white"
                    : i === stage
                      ? "animate-pulse bg-turmeric text-[#14261C]"
                      : "bg-mint"
                }`}
              >
                {i < stage ? "✓" : i + 1}
              </span>
              {s}
            </li>
          ))}
        </ol>
        <p className="text-xs text-muted">
          {elapsed}s elapsed · a full analysis usually takes one to three minutes.
          Stages are indicative, not live progress.
        </p>
      </div>
    </div>
  );
}
