"use client";

import type { AgentRun, StepStatus } from "./AgentProvider";
import { useAgent } from "./AgentProvider";

const STATUS_STYLE: Record<StepStatus, { dot: string; text: string; label: string }> = {
  queued: { dot: "border border-neutral-300 bg-white dark:bg-neutral-900", text: "text-neutral-500", label: "Queued" },
  running: { dot: "bg-green-600 animate-pulse", text: "text-neutral-900 dark:text-neutral-100", label: "Running" },
  completed: { dot: "bg-green-700", text: "text-neutral-700 dark:text-neutral-300", label: "Done" },
  failed: { dot: "bg-red-600", text: "text-red-700 dark:text-red-400", label: "Failed" },
  waiting_for_user: { dot: "bg-amber-500", text: "text-amber-800 dark:text-amber-300", label: "Waiting for you" },
  requires_confirmation: { dot: "bg-amber-500", text: "text-amber-800 dark:text-amber-300", label: "Needs confirmation" },
  skipped: { dot: "bg-neutral-300 dark:bg-neutral-700", text: "text-neutral-400 line-through", label: "Skipped" },
};

const RUN_LABEL: Record<AgentRun["status"], string> = {
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  waiting_for_user: "Waiting for you",
  requires_confirmation: "Needs confirmation",
  cancelled: "Cancelled",
};

export function ActivityTimeline({ run }: { run: AgentRun }) {
  return (
    <ol className="space-y-1.5" aria-label="Agent activity">
      {run.steps.map((s) => {
        const style = STATUS_STYLE[s.status];
        return (
          <li key={s.id} className="flex gap-2 text-xs">
            <span className={`mt-1 h-2 w-2 shrink-0 rounded-full ${style.dot}`} aria-hidden />
            <div className="min-w-0 flex-1">
              <div className={`flex items-center gap-2 ${style.text}`}>
                <span className="font-medium">{s.label}</span>
                <span className="sr-only">{style.label}</span>
                {s.status === "completed" && <span aria-hidden className="text-green-700">✓</span>}
              </div>
              {s.detail && s.status !== "waiting_for_user" && (
                <div className="truncate text-neutral-500" title={s.detail}>
                  {s.detail}
                </div>
              )}
              {s.substeps.length > 0 && (
                <ul className="mt-1 space-y-0.5 border-l border-neutral-200 pl-2 dark:border-neutral-800">
                  {s.substeps.map((x) => (
                    <li key={x.node} className="flex items-center gap-1.5 text-[11px] text-neutral-500">
                      <span
                        className={`h-1.5 w-1.5 rounded-full ${
                          x.status === "completed" ? "bg-green-700" : x.status === "failed" ? "bg-red-600" : "animate-pulse bg-green-500"
                        }`}
                      />
                      {x.label}
                    </li>
                  ))}
                </ul>
              )}
            </div>
          </li>
        );
      })}
    </ol>
  );
}

export function RunCard({ run }: { run: AgentRun }) {
  const { answerClarification, confirmRun, cancelRun } = useAgent();
  const active = run.status === "running" || run.status === "waiting_for_user" || run.status === "requires_confirmation";
  return (
    <div className="space-y-2 rounded border border-neutral-200 bg-white p-2.5 dark:border-neutral-800 dark:bg-neutral-950">
      <div className="flex items-center justify-between gap-2 text-[11px] uppercase tracking-wide text-neutral-500">
        <span>Agent run</span>
        <span
          className={
            run.status === "completed"
              ? "text-green-700"
              : run.status === "failed"
                ? "text-red-600"
                : run.status === "cancelled"
                  ? "text-neutral-400"
                  : "text-amber-700"
          }
        >
          {RUN_LABEL[run.status]}
        </span>
      </div>
      <ActivityTimeline run={run} />
      {run.error && <p className="text-xs text-red-700 dark:text-red-400">{run.error}</p>}
      {run.status === "requires_confirmation" && (
        <div className="flex gap-2">
          <button
            type="button"
            onClick={() => confirmRun(run.id)}
            className="rounded bg-green-700 px-2.5 py-1 text-xs font-medium text-white hover:bg-green-800"
          >
            Confirm and run
          </button>
          <button
            type="button"
            onClick={() => cancelRun(run.id)}
            className="rounded px-2.5 py-1 text-xs text-neutral-600 hover:bg-neutral-100 dark:text-neutral-300 dark:hover:bg-neutral-800"
          >
            Cancel
          </button>
        </div>
      )}
      {run.status === "waiting_for_user" && run.clarification && (
        <div className="space-y-2 rounded bg-amber-50 p-2 text-xs dark:bg-amber-950/40">
          <p className="text-amber-900 dark:text-amber-200">{run.clarification.question}</p>
          {run.clarification.options.length > 0 ? (
            <div className="flex flex-wrap gap-1.5">
              {run.clarification.options.map((o) => (
                <button
                  key={o.value}
                  type="button"
                  onClick={() => answerClarification(run.id, o.value)}
                  className={`rounded border border-amber-300 bg-white px-2 py-1 font-medium text-amber-900 hover:bg-amber-100 dark:border-amber-800 dark:bg-neutral-900 dark:text-amber-200 ${
                    run.clarification?.kind === "identity" ? "italic" : ""
                  }`}
                >
                  {o.label}
                </button>
              ))}
            </div>
          ) : (
            <p className="text-amber-800 dark:text-amber-300">Reply in the chat below.</p>
          )}
        </div>
      )}
      {active && run.status === "running" && (
        <button
          type="button"
          onClick={() => cancelRun(run.id)}
          className="text-[11px] text-neutral-500 hover:text-red-600"
        >
          Stop after current step
        </button>
      )}
    </div>
  );
}
