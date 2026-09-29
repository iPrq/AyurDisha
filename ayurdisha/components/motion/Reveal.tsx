"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, ScrollTrigger, useGSAP } from "@/lib/gsap";

/**
 * Fades and lifts every `[data-reveal]` descendant into view as it scrolls
 * onto the screen. Server-rendered children stay server components.
 */
export function Reveal({
  children,
  className,
  y = 32,
}: {
  children: React.ReactNode;
  className?: string;
  y?: number;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const items = gsap.utils.toArray<HTMLElement>("[data-reveal]", ref.current);
        gsap.set(items, { autoAlpha: 0, y });
        ScrollTrigger.batch(items, {
          start: "top 88%",
          once: true,
          onEnter: (batch) =>
            gsap.to(batch, {
              autoAlpha: 1,
              y: 0,
              duration: 0.8,
              stagger: 0.1,
              ease: "power3.out",
              overwrite: true,
            }),
        });
      });
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className={className}>
      {children}
    </div>
  );
}
