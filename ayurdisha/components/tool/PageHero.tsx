"use client";

import { useRef } from "react";
import { AskDishaHint } from "@/components/agent/AskDishaHint";
import { Dishu, type DishuPose } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

export function PageHero({
  eyebrow,
  title,
  desc,
  pose,
  assistant = true,
}: {
  eyebrow: string;
  title: string;
  desc: string;
  pose: DishuPose;
  /** Show the "Ask Disha" nudge under the description. */
  assistant?: boolean;
}) {
  const ref = useRef<HTMLDivElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(ref);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });
        gsap
          .timeline({ defaults: { ease: "power3.out" } })
          .from(q(".ph-text > *"), { y: 24, opacity: 0, stagger: 0.08, duration: 0.6 })
          .from(q(".ph-dishu"), { scale: 0.6, opacity: 0, duration: 0.6, ease: "back.out(1.8)" }, 0.15);
      });
    },
    { scope: ref },
  );

  return (
    <div ref={ref} className="flex items-center justify-between gap-6">
      <div data-reveal className="ph-text space-y-2">
        <p className="text-sm font-bold uppercase tracking-[0.18em] text-leaf">{eyebrow}</p>
        <h1 className="font-display text-[clamp(2rem,4.5vw,3rem)] font-extrabold leading-tight tracking-tight">
          {title}
        </h1>
        <p className="max-w-2xl text-muted">{desc}</p>
        {assistant && (
          <div className="pt-2">
            <AskDishaHint />
          </div>
        )}
      </div>
      <div data-reveal className="ph-dishu hidden w-32 shrink-0 sm:block">
        <Dishu pose={pose} className="h-auto w-full" />
      </div>
    </div>
  );
}
