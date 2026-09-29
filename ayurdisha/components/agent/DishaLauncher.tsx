"use client";

import { useEffect, useRef, useState } from "react";
import { Dishu } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

const INTRO_KEY = "disha-intro-seen";

function introSeen() {
  try {
    return localStorage.getItem(INTRO_KEY) === "1";
  } catch {
    return true;
  }
}

function markIntroSeen() {
  try {
    localStorage.setItem(INTRO_KEY, "1");
  } catch {
    // Storage unavailable (private mode): the intro simply shows again.
  }
}

/**
 * Closed-state launcher for the assistant: Dishu in a round button, plus a
 * one-time intro bubble so first-time visitors learn Disha exists.
 */
export function DishaLauncher({
  busy,
  onOpen,
}: {
  busy: boolean;
  onOpen: () => void;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const [intro, setIntro] = useState(false);

  useEffect(() => {
    if (introSeen()) return;
    const t = setTimeout(() => setIntro(true), 1400);
    return () => clearTimeout(t);
  }, []);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        gsap.from(".disha-launch", {
          y: 24,
          scale: 0.8,
          opacity: 0,
          duration: 0.6,
          ease: "back.out(1.8)",
          delay: 0.4,
        });
      });
    },
    { scope: ref },
  );

  useGSAP(
    () => {
      if (!intro) return;
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        gsap.from(".disha-bubble", {
          y: 12,
          scale: 0.9,
          opacity: 0,
          transformOrigin: "100% 100%",
          duration: 0.5,
          ease: "back.out(1.6)",
        });
      });
    },
    { scope: ref, dependencies: [intro] },
  );

  const open = () => {
    markIntroSeen();
    setIntro(false);
    onOpen();
  };

  const dismiss = () => {
    markIntroSeen();
    setIntro(false);
  };

  return (
    <div ref={ref} className="fixed bottom-10 right-6 z-40 flex flex-col items-end gap-3">
      {intro && (
        <div
          role="dialog"
          aria-label="Meet Disha"
          className="disha-bubble relative w-72 rounded-2xl border border-line bg-surface p-4 shadow-soft"
        >
          <p className="font-display font-bold">Hi, I&apos;m Disha.</p>
          <p className="mt-1 text-sm text-muted">
            Prefer talking to filling forms? Describe your product in your own
            words, typed or spoken, and I&apos;ll build the formulation and run the
            checks for you.
          </p>
          <div className="mt-3 flex gap-2">
            <button
              type="button"
              onClick={open}
              className="rounded-lg bg-ink px-3 py-1.5 text-sm font-semibold text-canvas hover:bg-leaf"
            >
              Show me how
            </button>
            <button
              type="button"
              onClick={dismiss}
              className="rounded-lg px-3 py-1.5 text-sm text-muted hover:bg-mint hover:text-ink"
            >
              Maybe later
            </button>
          </div>
          <span
            aria-hidden
            className="absolute -bottom-2 right-9 h-4 w-4 rotate-45 border-b border-r border-line bg-surface"
          />
        </div>
      )}

      <button
        type="button"
        onClick={open}
        aria-label="Ask Disha, the AyurDisha assistant (Ctrl K)"
        className="disha-launch group flex items-center gap-3 rounded-full border border-line bg-surface py-1.5 pl-5 pr-1.5 shadow-soft transition-transform hover:-translate-y-0.5"
      >
        <span className="text-left leading-tight">
          <span className="block text-sm font-bold">Ask Disha</span>
          <span className="block text-[11px] text-muted">
            {busy ? "Working on it…" : "Your assistant · Ctrl K"}
          </span>
        </span>
        <span className="relative grid h-14 w-14 place-items-center rounded-full bg-mint ring-2 ring-leaf-bright/40 transition-colors group-hover:bg-blob">
          <Dishu pose={busy ? "think" : "wave"} size={48} title="" />
          {busy && (
            <span className="absolute right-0.5 top-0.5 h-3 w-3 animate-pulse rounded-full border-2 border-surface bg-turmeric" />
          )}
        </span>
      </button>
    </div>
  );
}
