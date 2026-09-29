"use client";

import { createContext, useCallback, useContext, useSyncExternalStore } from "react";
import type { LegalScope } from "@/lib/types";

const STORAGE_KEY = "ayurdisha-source-scope";

type SourceScopeValue = {
  scope: LegalScope;
  setScope: (scope: LegalScope) => void;
};

const SourceScopeContext = createContext<SourceScopeValue | null>(null);

/**
 * One site-wide choice of Indian vs international sources, shared by every
 * tool and remembered in the browser.
 */
const CHANGE_EVENT = "ayurdisha-source-scope";
let memoryScope: LegalScope = "domestic"; // fallback when storage is unavailable

function readScope(): LegalScope {
  try {
    const saved = localStorage.getItem(STORAGE_KEY);
    if (saved === "domestic" || saved === "international") return saved;
  } catch {
    // Storage unavailable: fall through to the in-memory value.
  }
  return memoryScope;
}

function subscribe(onChange: () => void) {
  window.addEventListener(CHANGE_EVENT, onChange);
  window.addEventListener("storage", onChange); // other tabs
  return () => {
    window.removeEventListener(CHANGE_EVENT, onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function SourceScopeProvider({ children }: { children: React.ReactNode }) {
  const scope = useSyncExternalStore(subscribe, readScope, () => "domestic" as const);

  const setScope = useCallback((next: LegalScope) => {
    memoryScope = next;
    try {
      localStorage.setItem(STORAGE_KEY, next);
    } catch {
      // Storage unavailable: the choice lasts for this visit only.
    }
    window.dispatchEvent(new Event(CHANGE_EVENT));
  }, []);

  return (
    <SourceScopeContext.Provider value={{ scope, setScope }}>
      {children}
    </SourceScopeContext.Provider>
  );
}

export function useSourceScope(): SourceScopeValue {
  const ctx = useContext(SourceScopeContext);
  if (!ctx) throw new Error("useSourceScope must be used inside SourceScopeProvider");
  return ctx;
}
