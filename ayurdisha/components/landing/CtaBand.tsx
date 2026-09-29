"use client";

import Link from "next/link";
import { useRef } from "react";
import { Dishu } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

const CONFETTI = ["#F2A93B", "#8BD6A3", "#E07A50", "#5B8DEF", "#6CC58C", "#FFF8E7"];

export function CtaBand() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });
        gsap
          .timeline({
            scrollTrigger: { trigger: root.current, start: "top 75%", once: true },
          })
          .from(q(".cta-panel"), { y: 60, opacity: 0, duration: 0.8, ease: "power3.out" })
          .from(q(".cta-dishu"), { y: 80, opacity: 0, duration: 0.7, ease: "back.out(1.8)" }, "-=0.3")
          .fromTo(
            q(".cta-confetti"),
            { x: 0, y: 0, rotation: 0, opacity: 1, scale: 0.4 },
            {
              x: () => gsap.utils.random(-220, 220),
              y: () => gsap.utils.random(-200, -40),
              rotation: () => gsap.utils.random(-360, 360),
              scale: 1,
              opacity: 0,
              duration: 1.6,
              stagger: 0.02,
              ease: "power3.out",
            },
            "-=0.4",
          );
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} className="mx-auto max-w-6xl px-4 pb-24 sm:px-6">
      <div
        data-reveal
        className="cta-panel relative grid items-center gap-8 overflow-hidden rounded-[2.5rem] bg-leaf px-8 py-12 text-canvas sm:px-12 md:grid-cols-[1fr_auto]"
      >
        <svg aria-hidden viewBox="0 0 400 400" className="pointer-events-none absolute -right-24 -top-24 h-96 w-96 opacity-15">
          <circle cx="200" cy="200" r="150" fill="none" stroke="currentColor" strokeWidth="40" />
        </svg>
        <div className="relative space-y-4">
          <h2 className="font-display text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-tight tracking-tight">
            Ready to find your direction?
          </h2>
          <p className="max-w-lg text-lg opacity-85">
            Run a product review in minutes. Upload a dossier or type a few
            ingredients, and get a cited report you can take to your advisors.
          </p>
          <div className="flex flex-wrap gap-3 pt-2">
            <Link
              href="/review"
              className="rounded-full bg-turmeric px-7 py-3.5 font-semibold text-[#14261C] shadow-soft transition-transform hover:-translate-y-0.5"
            >
              Start a product review
            </Link>
            <Link
              href="/nba-abs"
              className="rounded-full border-2 border-current px-7 py-3 font-semibold transition-opacity hover:opacity-80"
            >
              Check ABS obligations
            </Link>
          </div>
        </div>
        <div className="relative mx-auto w-44 md:w-52">
          <div className="absolute left-1/2 top-1/2" aria-hidden>
            {Array.from({ length: 18 }, (_, i) => (
              <span
                key={i}
                className="cta-confetti absolute block h-3 w-5 rounded-[60%_0] opacity-0"
                style={{ backgroundColor: CONFETTI[i % CONFETTI.length] }}
              />
            ))}
          </div>
          <div className="cta-dishu">
            <Dishu pose="celebrate" className="h-auto w-full" />
          </div>
        </div>
      </div>
    </section>
  );
}
