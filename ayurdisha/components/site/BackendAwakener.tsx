"use client";

import { useState, useEffect, useCallback } from "react";
import { Dishu } from "@/components/mascot/Dishu";

const FUNKY_TEXTS = [
  "Grinding the herbs... 🌿",
  "Brewing the formulation... 💊",
  "Extracting the compounds... 🧪",
  "Reading the patents... 📜",
  "Checking the corpus documents... 📄",
  "Categorizing therapeutics... 🏷️",
  "Translating vernacular names... 🔤",
  "Packaging the product... 📦",
];

/** Directly ping the Render backend from the browser — no Vercel middleman. */
async function pingDirect(): Promise<boolean> {
  try {
    const controller = new AbortController();
    const tid = setTimeout(() => controller.abort(), 3000);
    const res = await fetch("/api/ping", {
      signal: controller.signal,
      cache: "no-store",
    });
    clearTimeout(tid);
    return res.ok;
  } catch {
    return false;
  }
}

export function BackendAwakener() {
  const [status, setStatus] = useState<"checking" | "waking" | "ready">("checking");
  const [elapsed, setElapsed] = useState(0);
  const [textIndex, setTextIndex] = useState(0);
  const [dismissed, setDismissed] = useState(false);

  const ESTIMATED = 50;

  const check = useCallback(async () => {
    const ok = await pingDirect();
    if (ok) setStatus("ready");
    return ok;
  }, []);

  // Initial check + fast polling
  useEffect(() => {
    let mounted = true;
    let timer: ReturnType<typeof setTimeout>;

    const poll = async () => {
      const ok = await check();
      if (!mounted) return;
      if (ok) return; // done
      if (status === "checking") setStatus("waking");
      // Poll again in 3s (fast)
      timer = setTimeout(poll, 3000);
    };

    poll();

    return () => {
      mounted = false;
      clearTimeout(timer);
    };
  }, [check, status]);

  // Elapsed timer + text cycler
  useEffect(() => {
    if (status !== "waking") return;
    const tick = setInterval(() => setElapsed((s) => s + 1), 1000);
    const txt = setInterval(() => setTextIndex((i) => (i + 1) % FUNKY_TEXTS.length), 3500);
    return () => {
      clearInterval(tick);
      clearInterval(txt);
    };
  }, [status]);

  // Don't render anything if ready, dismissed, or still doing the first instant check
  if (status === "ready" || dismissed || status === "checking") return null;

  const progress = Math.min(98, (elapsed / ESTIMATED) * 100); // never show 100% — that implies done
  const remaining = Math.max(1, ESTIMATED - elapsed);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-canvas/60 backdrop-blur-lg">
      <div className="relative mx-4 flex w-full max-w-md flex-col items-center overflow-hidden rounded-2xl border border-line bg-surface p-8 text-center shadow-2xl">
        {/* Mascot */}
        <div className="mb-5">
          <Dishu size={96} pose="think" animated />
        </div>

        <h2 className="mb-1 font-display text-xl font-bold tracking-tight text-ink">
          Waking up the server
        </h2>

        <p className="mb-6 h-5 text-sm font-medium text-leaf">
          {FUNKY_TEXTS[textIndex]}
        </p>

        {/* Progress bar */}
        <div className="w-full">
          <div className="mb-1.5 flex justify-between text-[11px] font-medium uppercase tracking-wider text-muted">
            <span>Loading</span>
            <span>~{remaining}s</span>
          </div>
          <div className="h-2 w-full overflow-hidden rounded-full bg-line">
            <div
              className="h-full rounded-full bg-leaf transition-[width] duration-1000 ease-linear"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>

        {/* Skip button — shows after 10 seconds */}
        {elapsed >= 10 && (
          <button
            type="button"
            onClick={() => setDismissed(true)}
            className="mt-5 rounded-lg border border-line px-4 py-1.5 text-xs font-medium text-muted transition-colors hover:bg-mint hover:text-ink"
          >
            Skip — browse anyway
          </button>
        )}

        <p className="mt-4 text-[11px] italic text-muted/60">
          Free-tier servers sleep after 15 min of inactivity
        </p>
      </div>
    </div>
  );
}
