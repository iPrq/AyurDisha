"use client";

import Link from "next/link";
import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";
import { Accent } from "./SectionHeading";

// Illustrative values only; the card is labelled as an example on the page.
const SCORE = 0.46;

// Same thresholds the Patent Advisor page uses to colour its risk bar.
const BANDS = [
  { label: "Low", from: 0, to: 0.3 },
  { label: "Moderate", from: 0.3, to: 0.6 },
  { label: "High", from: 0.6, to: 1 },
];

const STATUS = {
  triggered: { text: "Triggered", dot: "bg-clay", ink: "text-[#A5401A]" },
  gap: { text: "Evidence gap", dot: "bg-turmeric", ink: "text-turmeric-ink" },
  clear: { text: "Not triggered", dot: "bg-leaf-bright", ink: "text-leaf" },
} as const;

const CLAUSES: {
  clause: string;
  name: string;
  reason: string;
  status: keyof typeof STATUS;
}[] = [
  {
    clause: "3(d)",
    name: "New form of a known substance",
    reason: "No data showing enhanced efficacy over curcumin alone.",
    status: "triggered",
  },
  {
    clause: "3(e)",
    name: "Mere admixture",
    reason: "Turmeric and neem effects look additive, not synergistic.",
    status: "triggered",
  },
  {
    clause: "3(p)",
    name: "Traditional knowledge",
    reason: "Both herbs appear in classical wound-care texts. Needs review.",
    status: "gap",
  },
  {
    clause: "3(i)",
    name: "Method of treatment",
    reason: "Claims cover a product, not a treatment method.",
    status: "clear",
  },
];

export function RiskShowcase() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

        gsap.from(q(".risk-copy > *"), {
          y: 24,
          opacity: 0,
          stagger: 0.08,
          duration: 0.7,
          ease: "power3.out",
          scrollTrigger: { trigger: root.current, start: "top 75%", once: true },
        });

        const score = q(".risk-score")[0];
        const counter = { v: 0 };
        gsap
          .timeline({
            defaults: { ease: "power3.out" },
            scrollTrigger: { trigger: q(".risk-card")[0], start: "top 75%", once: true },
          })
          .from(q(".risk-card"), { y: 40, opacity: 0, duration: 0.7 })
          .from(q(".risk-fill"), { scaleX: 0, transformOrigin: "0% 50%", duration: 1, ease: "power2.inOut" }, 0.3)
          .from(q(".risk-marker"), { left: "0%", duration: 1, ease: "power2.inOut" }, 0.3)
          .to(
            counter,
            {
              v: SCORE,
              duration: 1,
              ease: "power2.inOut",
              onUpdate: () => {
                if (score) score.textContent = counter.v.toFixed(2);
              },
            },
            0.3,
          )
          .from(q(".risk-row"), { y: 10, opacity: 0, stagger: 0.1, duration: 0.5 }, 0.8)
          .from(q(".risk-route"), { opacity: 0, duration: 0.5 }, "-=0.1");
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} className="mx-auto max-w-6xl overflow-x-clip px-4 py-24 sm:px-6">
      <div className="grid items-center gap-14 lg:grid-cols-[0.9fr_1.1fr]">
        <div data-reveal className="risk-copy space-y-5">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-leaf">
            Patent Advisor
          </p>
          <h2 className="font-display text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-tight tracking-tight">
            Know your risk <Accent>before</Accent> you file
          </h2>
          <p className="text-lg text-muted">
            A rule-based Section 3 indicator tells you which provisions of the
            Indian Patents Act your invention may run into, and why, with the
            statute text and examination guidelines cited next to every finding.
          </p>
          <p className="text-muted">
            Covers all 15 active clauses of Section 3, from 3(a) to 3(p).
          </p>
          <Link
            href="/patent"
            className="inline-block rounded-full bg-turmeric px-6 py-3 font-semibold text-[#14261C] shadow-soft transition-transform hover:-translate-y-0.5 hover:bg-turmeric-deep"
          >
            Check my invention
          </Link>
        </div>

        <div data-reveal className="relative">
          {/* A second sheet behind the card, like a printed report. */}
          <div
            aria-hidden
            className="absolute inset-0 translate-x-3 translate-y-3 rounded-2xl border border-line bg-mint"
          />
          <article className="risk-card relative rounded-2xl border border-line bg-surface p-6 shadow-soft sm:p-8">
            <header className="flex flex-wrap items-baseline justify-between gap-2 border-b border-line pb-4">
              <div>
                <p className="text-xs font-semibold uppercase tracking-wider text-muted">
                  Example report
                </p>
                <h3 className="font-display text-lg font-bold">
                  Turmeric + neem wound-healing gel
                </h3>
              </div>
              <p className="text-xs text-muted">Patent Advisor · India</p>
            </header>

            <div className="py-5">
              <div className="flex items-baseline gap-3">
                <p className="text-sm font-semibold text-muted">Section 3 risk</p>
                <p className="ml-auto font-display text-3xl font-extrabold tabular-nums">
                  <span className="risk-score">{SCORE.toFixed(2)}</span>
                </p>
                <p className="text-sm font-semibold text-turmeric-ink">Moderate</p>
              </div>

              <div className="relative mt-4">
                <div className="flex h-2 overflow-hidden rounded-full bg-mint">
                  <div
                    className="risk-fill h-full rounded-full bg-turmeric"
                    style={{ width: `${SCORE * 100}%` }}
                  />
                </div>
                <div
                  className="risk-marker absolute -top-1.5 h-5 w-0.5 -translate-x-1/2 rounded bg-ink"
                  style={{ left: `${SCORE * 100}%` }}
                  aria-hidden
                />
                <div className="mt-2 flex text-[11px] text-muted">
                  {BANDS.map((b) => (
                    <span
                      key={b.label}
                      style={{ width: `${(b.to - b.from) * 100}%` }}
                      className="border-l border-line pl-1.5 first:border-l-0 first:pl-0"
                    >
                      {b.label}
                    </span>
                  ))}
                </div>
              </div>
            </div>

            <table className="w-full text-left text-sm">
              <thead>
                <tr className="text-[11px] uppercase tracking-wider text-muted">
                  <th className="pb-2 font-semibold">Clause</th>
                  <th className="pb-2 font-semibold">Finding</th>
                  <th className="pb-2 text-right font-semibold">Status</th>
                </tr>
              </thead>
              <tbody>
                {CLAUSES.map((c) => {
                  const s = STATUS[c.status];
                  return (
                    <tr key={c.clause} className="risk-row border-t border-line align-top">
                      <td className="py-3 pr-3 font-mono text-sm font-semibold">{c.clause}</td>
                      <td className="py-3 pr-3">
                        <span className="block font-medium">{c.name}</span>
                        <span className="block text-xs text-muted">{c.reason}</span>
                      </td>
                      <td className={`whitespace-nowrap py-3 text-right text-xs font-semibold ${s.ink}`}>
                        <span className={`mr-1.5 inline-block h-1.5 w-1.5 rounded-full align-middle ${s.dot}`} />
                        {s.text}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>

            <div className="risk-route mt-4 border-t border-line pt-4 text-sm">
              <span className="font-semibold">Suggested route: </span>
              <span className="text-muted">
                keep it as a trade secret for now, and revisit a patent once you
                have efficacy data showing an enhanced therapeutic effect.
              </span>
            </div>

            <p className="mt-4 text-[11px] text-muted">
              Illustrative example. A rule-based risk indicator, not a probability
              of grant.
            </p>
          </article>
        </div>
      </div>
    </section>
  );
}
