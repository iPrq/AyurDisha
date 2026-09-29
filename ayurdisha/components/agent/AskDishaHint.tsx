"use client";

import { useAgent } from "./AgentProvider";

/** Inline nudge on tool pages: the form works, but Disha can do it for you. */
export function AskDishaHint() {
  const { setDockOpen } = useAgent();
  return (
    <button
      type="button"
      onClick={() => setDockOpen(true)}
      className="group inline-flex items-center gap-2 rounded-full border border-dashed border-leaf-bright/50 bg-surface px-3.5 py-1.5 text-sm text-muted transition-colors hover:border-leaf-bright hover:text-ink"
    >
      <span className="h-2 w-2 rounded-full bg-leaf-bright" />
      Rather describe it in your own words?
      <span className="font-semibold text-leaf">
        Ask Disha{" "}
        <span className="inline-block transition-transform group-hover:translate-x-0.5">→</span>
      </span>
    </button>
  );
}
