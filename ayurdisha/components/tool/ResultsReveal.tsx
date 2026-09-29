"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

/** Staggers result cards in when an analysis finishes. */
export function ResultsReveal({ children }: { children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        gsap.from(gsap.utils.toArray<HTMLElement>(".result-section", ref.current), {
          y: 28,
          opacity: 0,
          duration: 0.6,
          stagger: 0.08,
          ease: "power3.out",
          clearProps: "transform,opacity",
        });
      });
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      ref.current?.scrollIntoView({ behavior: reduce ? "auto" : "smooth", block: "start" });
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className="scroll-mt-24">
      {children}
    </div>
  );
}
