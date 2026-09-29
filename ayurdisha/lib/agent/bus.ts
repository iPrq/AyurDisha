import type { StepEvent } from "@/lib/formulation/sse";
import type { ToolHandoff, ToolName } from "@/lib/formulation/types";

/**
 * Typed capability bus between the agent executor and tool pages.
 * Pages expose a fixed set of capabilities; the agent can only call those — there is no
 * generic event, selector or script channel.
 */
export interface ToolRunOutcome {
  summary: string;
}

export interface ToolCapabilities {
  autofill: (handoff: ToolHandoff) => Promise<void>;
  run: (progress: {
    started: (e: StepEvent) => void;
    completed: (e: StepEvent) => void;
    failed: (e: StepEvent) => void;
  }) => Promise<ToolRunOutcome>;
}

type Listener = () => void;

const handlers = new Map<ToolName, ToolCapabilities>();
const listeners = new Set<Listener>();

export function registerTool(tool: ToolName, caps: ToolCapabilities): () => void {
  handlers.set(tool, caps);
  listeners.forEach((l) => l());
  return () => {
    if (handlers.get(tool) === caps) handlers.delete(tool);
  };
}

export function hasTool(tool: ToolName): boolean {
  return handlers.has(tool);
}

/** Resolves with the page's capabilities once it has mounted, or rejects after `timeoutMs`. */
export function waitForTool(tool: ToolName, timeoutMs = 8000): Promise<ToolCapabilities> {
  const existing = handlers.get(tool);
  if (existing) return Promise.resolve(existing);
  return new Promise((resolve, reject) => {
    const check: Listener = () => {
      const caps = handlers.get(tool);
      if (caps) {
        clearTimeout(timer);
        listeners.delete(check);
        resolve(caps);
      }
    };
    const timer = setTimeout(() => {
      listeners.delete(check);
      reject(new Error("The tool page did not become ready."));
    }, timeoutMs);
    listeners.add(check);
  });
}
