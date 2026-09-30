"use client";

import { useState, useEffect } from "react";
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

export function BackendAwakener() {
  const [status, setStatus] = useState<"checking" | "waking" | "ready">("checking");
  const [secondsAwake, setSecondsAwake] = useState(0);
  const [textIndex, setTextIndex] = useState(0);
  
  // Total estimated wake up time for Render free tier is ~50 seconds.
  const ESTIMATED_TIME = 50;

  useEffect(() => {
    let mounted = true;
    let pollInterval: NodeJS.Timeout;

    const pingBackend = async () => {
      try {
        const res = await fetch("/api/ping");
        if (res.ok) {
          if (mounted) setStatus("ready");
          return true;
        }
      } catch (e) {
        // network error / timeout
      }
      return false;
    };

    const initialCheck = async () => {
      const isAwake = await pingBackend();
      if (!isAwake && mounted) {
        setStatus("waking");
        // Start polling every 5 seconds
        pollInterval = setInterval(async () => {
          const awake = await pingBackend();
          if (awake) {
            clearInterval(pollInterval);
          }
        }, 5000);
      }
    };

    initialCheck();

    return () => {
      mounted = false;
      if (pollInterval) clearInterval(pollInterval);
    };
  }, []);

  // Timer & Text cycler when waking
  useEffect(() => {
    if (status !== "waking") return;
    
    const timer = setInterval(() => {
      setSecondsAwake((s) => s + 1);
    }, 1000);

    const texter = setInterval(() => {
      setTextIndex((i) => (i + 1) % FUNKY_TEXTS.length);
    }, 4000); // Change text every 4 seconds

    return () => {
      clearInterval(timer);
      clearInterval(texter);
    };
  }, [status]);

  if (status === "ready") return null;

  // Don't show heavy UI for the first split-second of "checking", only show when "waking"
  if (status === "checking") return null;

  const progress = Math.min(100, (secondsAwake / ESTIMATED_TIME) * 100);
  const remaining = Math.max(0, ESTIMATED_TIME - secondsAwake);

  return (
    <div className="fixed inset-0 z-[9999] flex items-center justify-center bg-canvas/40 backdrop-blur-xl transition-opacity duration-500">
      <div className="relative mx-4 flex w-full max-w-md flex-col items-center overflow-hidden rounded-[2rem] border border-line bg-surface/90 p-8 text-center shadow-[0_20px_50px_rgba(0,0,0,0.1)] backdrop-blur-2xl">
        <div className="mb-6 flex items-center justify-center">
          <Dishu size={100} pose="think" animated={true} />
        </div>
        
        <h2 className="mb-2 font-display text-2xl font-bold tracking-tight text-ink">
          Awakening the Backend
        </h2>
        
        <p className="mb-8 h-6 text-sm font-medium text-leaf transition-all duration-300">
          {FUNKY_TEXTS[textIndex]}
        </p>
        
        <div className="w-full">
          <div className="mb-2 flex justify-between text-xs font-bold uppercase tracking-wider text-muted">
            <span>Loading</span>
            <span>~{remaining}s remaining</span>
          </div>
          <div className="h-2.5 w-full overflow-hidden rounded-full bg-line shadow-inner">
            <div 
              className="h-full rounded-full bg-gradient-to-r from-leaf to-leaf-bright transition-all duration-1000 ease-linear"
              style={{ width: `${progress}%` }}
            />
          </div>
        </div>
        
        <p className="mt-6 text-[11px] text-muted/70 italic">
          (Free-tier servers sleep after 15m of inactivity)
        </p>
      </div>
    </div>
  );
}
