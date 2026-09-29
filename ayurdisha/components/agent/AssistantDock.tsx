"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { languageApi } from "@/lib/formulation/api";
import { LANGUAGE_OPTIONS, type LanguageCapabilities } from "@/lib/formulation/types";
import { RunCard } from "./ActivityTimeline";
import { useAgent } from "./AgentProvider";
import { VoiceButton } from "./VoiceButton";

const SLASH_COMMANDS = [
  { cmd: "/formulation", hint: "Open the formulation map" },
  { cmd: "/review", hint: "Run Product Review on the formulation" },
  { cmd: "/patent", hint: "Run Patent Advisor on the formulation" },
  { cmd: "/abs", hint: "Check NBA / ABS applicability" },
  { cmd: "/evidence", hint: "Open the evidence panel" },
];

const EXAMPLES = [
  "Ashwagandha root 300 mg and turmeric 200 mg capsule for stress support",
  "Add guduchi 100 mg",
  "Check patent risk",
];

export function AssistantDock() {
  const { dockOpen, setDockOpen, messages, runs, busy, send, language, setLanguage, formulation } = useAgent();
  const [draft, setDraft] = useState("");
  const [caps, setCaps] = useState<LanguageCapabilities | null>(null);
  const scrollRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (!dockOpen || caps) return;
    languageApi.capabilities().then(setCaps).catch(() => setCaps(null));
  }, [dockOpen, caps]);

  useEffect(() => {
    scrollRef.current?.scrollTo({ top: scrollRef.current.scrollHeight, behavior: "smooth" });
  }, [messages, runs]);

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setDockOpen(true);
        setTimeout(() => inputRef.current?.focus(), 0);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [setDockOpen]);

  const runsById = useMemo(() => new Map(runs.map((r) => [r.id, r])), [runs]);
  const activeRun = runs.find((r) => r.status === "running");
  const status = activeRun ? "Updating" : busy ? "Understanding" : null;
  const slashMatches = draft.startsWith("/") && !draft.includes(" ")
    ? SLASH_COMMANDS.filter((c) => c.cmd.startsWith(draft.toLowerCase()))
    : [];

  const submit = (text = draft) => {
    const t = text.trim();
    if (!t || busy) return;
    setDraft("");
    void send(t);
  };

  const asrReason = caps
    ? caps.asr
      ? ""
      : `Voice input needs a speech service (${caps.provider} provider has no ASR). ${caps.notes[0] ?? ""}`.trim()
    : "Checking voice availability…";

  if (!dockOpen) {
    return (
      <button
        type="button"
        onClick={() => setDockOpen(true)}
        className="fixed bottom-5 right-5 z-40 flex items-center gap-2 rounded-full bg-green-800 px-4 py-2.5 text-sm font-medium text-white shadow-lg hover:bg-green-900"
        aria-label="Open AyurDisha assistant"
      >
        <span className={`h-2 w-2 rounded-full ${activeRun ? "animate-pulse bg-amber-300" : "bg-green-300"}`} />
        Assistant
        <kbd className="rounded bg-green-900 px-1 text-[10px] text-green-200">Ctrl K</kbd>
      </button>
    );
  }

  return (
    <aside
      className="fixed bottom-0 right-0 top-0 z-40 flex w-full flex-col border-l border-neutral-200 bg-neutral-50 shadow-xl sm:w-[380px] dark:border-neutral-800 dark:bg-neutral-950"
      aria-label="AyurDisha assistant"
    >
      <header className="flex items-center gap-2 border-b border-neutral-200 px-3 py-2 dark:border-neutral-800">
        <div className="min-w-0 flex-1">
          <div className="text-sm font-semibold text-green-800 dark:text-green-400">AyurDisha Assistant</div>
          <div className="truncate text-[11px] text-neutral-500">
            {formulation
              ? `Formulation v${formulation.version} · ${formulation.ingredients.length} ingredient${formulation.ingredients.length === 1 ? "" : "s"}`
              : "No formulation yet"}
          </div>
        </div>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          aria-label="Language"
          className="max-w-[120px] rounded border border-neutral-300 bg-white px-1.5 py-1 text-xs dark:border-neutral-700 dark:bg-neutral-900"
        >
          {LANGUAGE_OPTIONS.map((l) => (
            <option key={l.code} value={l.code}>
              {l.name}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={() => setDockOpen(false)}
          className="rounded px-2 py-1 text-neutral-500 hover:bg-neutral-200 dark:hover:bg-neutral-800"
          aria-label="Close assistant"
        >
          ×
        </button>
      </header>

      {caps && language !== "auto" && language !== "en" && !caps.translation && (
        <div className="border-b border-amber-200 bg-amber-50 px-3 py-1.5 text-[11px] text-amber-900 dark:border-amber-900 dark:bg-amber-950/40 dark:text-amber-200">
          Translation service is not configured — requests in this language are interpreted as written, and replies stay in English.
        </div>
      )}

      <div ref={scrollRef} className="flex-1 space-y-3 overflow-y-auto px-3 py-3">
        {messages.length === 0 && (
          <div className="space-y-2 text-sm text-neutral-600 dark:text-neutral-400">
            <p>
              Describe a formulation or ask me to act on it. I update the formulation, open tools and run them — every
              step is shown below as it actually happens.
            </p>
            <div className="space-y-1">
              {EXAMPLES.map((ex) => (
                <button
                  key={ex}
                  type="button"
                  onClick={() => submit(ex)}
                  className="block w-full rounded border border-neutral-200 bg-white px-2 py-1.5 text-left text-xs hover:border-green-600 dark:border-neutral-800 dark:bg-neutral-900"
                >
                  {ex}
                </button>
              ))}
            </div>
          </div>
        )}
        {messages.map((m) => {
          const run = m.runId && m.role === "assistant" ? runsById.get(m.runId) : undefined;
          return (
            <div key={m.id} className={m.role === "user" ? "flex justify-end" : "space-y-2"}>
              <div
                className={
                  m.role === "user"
                    ? "max-w-[85%] rounded-lg bg-green-800 px-3 py-1.5 text-sm text-white"
                    : "text-sm text-neutral-800 dark:text-neutral-200"
                }
              >
                {m.text}
                {m.subtext && (
                  <div className={`mt-0.5 text-[11px] ${m.role === "user" ? "text-green-200" : "text-neutral-500"}`}>
                    {m.subtext}
                  </div>
                )}
              </div>
              {run && <RunCard run={run} />}
            </div>
          );
        })}
      </div>

      <div className="border-t border-neutral-200 p-2 dark:border-neutral-800">
        {status && (
          <div className="mb-1 flex items-center gap-1.5 px-1 text-[11px] text-neutral-500">
            <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-green-600" />
            {status}…
          </div>
        )}
        {slashMatches.length > 0 && (
          <ul className="mb-1 rounded border border-neutral-200 bg-white text-xs dark:border-neutral-800 dark:bg-neutral-900">
            {slashMatches.map((c) => (
              <li key={c.cmd}>
                <button
                  type="button"
                  onClick={() => submit(c.cmd)}
                  className="flex w-full gap-2 px-2 py-1.5 text-left hover:bg-neutral-100 dark:hover:bg-neutral-800"
                >
                  <span className="font-mono text-green-800 dark:text-green-400">{c.cmd}</span>
                  <span className="text-neutral-500">{c.hint}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
        <div className="flex items-end gap-2">
          <textarea
            ref={inputRef}
            rows={2}
            value={draft}
            onChange={(e) => setDraft(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && !e.shiftKey) {
                e.preventDefault();
                submit();
              }
            }}
            placeholder="Describe, change or run… ( / for commands)"
            className="min-h-[40px] flex-1 resize-none rounded border border-neutral-300 bg-white px-2 py-1.5 text-sm focus:border-green-700 focus:outline-none dark:border-neutral-700 dark:bg-neutral-900"
          />
          <VoiceButton
            language={language}
            asrAvailable={!!caps?.asr}
            unavailableReason={asrReason}
            disabled={busy}
            onTranscript={(text, detected) =>
              void send(text, { source: "voice", originalText: text, language: language === "auto" ? detected : language })
            }
          />
          <button
            type="button"
            onClick={() => submit()}
            disabled={busy || !draft.trim()}
            className="h-8 rounded bg-green-700 px-3 text-sm font-medium text-white hover:bg-green-800 disabled:opacity-40"
          >
            Send
          </button>
        </div>
      </div>
    </aside>
  );
}
