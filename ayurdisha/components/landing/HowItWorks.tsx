"use client";

import { useRef } from "react";
import {
  BookSearchIcon,
  ClipboardIcon,
  LeafTagIcon,
  UploadDocIcon,
} from "@/components/icons/SpotIcons";
import { Dishu } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";
import { drawIcons } from "@/lib/motion";
import { Accent } from "./SectionHeading";

const STEPS = [
  {
    title: "Describe or upload",
    desc: "Enter the product and ingredients, or upload a PDF dossier. Scanned pages are OCR'd and pre-fill the form.",
    Icon: UploadDocIcon,
  },
  {
    title: "Normalise botanicals",
    desc: "Common and Sanskrit names are matched to botanical names. Ambiguous herbs are escalated, never guessed.",
    Icon: LeafTagIcon,
  },
  {
    title: "Retrieve evidence",
    desc: "Hybrid search over statutes, pharmacopoeias, guidelines, case law and patents, filtered by Indian or international scope.",
    Icon: BookSearchIcon,
  },
  {
    title: "Verified, cited report",
    desc: "Scores and findings are checked by a verifier that strips any claim without a supporting source.",
    Icon: ClipboardIcon,
  },
];

// Wave through the four step icons (column centres at 12.5% / 37.5% / ...).
const VINE = "M125 60 C200 -10 300 -10 375 60 S550 130 625 60 S800 -10 875 60";

export function HowItWorks() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(
        { motion: MOTION_OK, wide: "(min-width: 1024px)" },
        (ctx) => {
          const { motion, wide } = ctx.conditions as { motion: boolean; wide: boolean };
          if (!motion) return;
          const q = gsap.utils.selector(root);
          gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

          gsap.from(q(".how-head > *"), {
            y: 30,
            opacity: 0,
            stagger: 0.1,
            duration: 0.8,
            ease: "power3.out",
            scrollTrigger: { trigger: q(".how-head")[0], start: "top 85%", once: true },
          });

          const steps = q(".how-step");
          if (!wide) {
            // Stacked layout: plain reveal per step, no vine.
            steps.forEach((el) => {
              const t = gsap.timeline({
                scrollTrigger: { trigger: el, start: "top 85%", once: true },
              });
              t.from(el, { opacity: 0, y: 30, duration: 0.7, ease: "power3.out" });
              drawIcons(t, el.querySelector(".how-icon"), 0.15);
            });
            return;
          }

          const vine = q(".how-vine")[0] as unknown as SVGPathElement;
          const tl = gsap.timeline({
            defaults: { ease: "none" },
            scrollTrigger: {
              trigger: q(".how-track")[0],
              start: "top 75%",
              end: "bottom 45%",
              scrub: 0.6,
            },
          });
          tl.fromTo(vine, { drawSVG: "0%" }, { drawSVG: "100%", duration: 1 }, 0).to(
            q(".how-traveller"),
            {
              duration: 1,
              immediateRender: true,
              // Walk between the first and last icons without covering them.
              motionPath: {
                path: vine,
                align: vine,
                alignOrigin: [0.5, 0.92],
                start: 0.1,
                end: 0.9,
              },
            },
            0,
          );
          steps.forEach((el, i) => {
            const at = Math.max(0, i * 0.3 - 0.05);
            tl.from(el, { opacity: 0, y: 40, duration: 0.18, ease: "power2.out" }, at);
            drawIcons(tl, el.querySelector(".how-icon"), at + 0.04, 0.16);
          });
        },
      );
    },
    { scope: root },
  );

  return (
    <section ref={root} className="bg-mint py-24">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="how-head mx-auto max-w-2xl space-y-3 text-center">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-leaf">
            How it works
          </p>
          <h2 className="font-display text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-tight tracking-tight">
            From a product idea to a <Accent>cited</Accent> answer
          </h2>
          <p className="text-lg text-muted">
            A LangGraph pipeline does the reading, so you can focus on the
            decision.
          </p>
        </div>

        <div className="how-track relative mt-14">
          <svg
            viewBox="0 0 1000 120"
            preserveAspectRatio="none"
            className="pointer-events-none absolute inset-x-0 top-0 hidden h-[120px] w-full lg:block"
            aria-hidden
          >
            <path
              d={VINE}
              fill="none"
              stroke="var(--line)"
              strokeWidth="4"
              strokeDasharray="2 10"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
            <path
              className="how-vine"
              d={VINE}
              fill="none"
              stroke="var(--leaf-bright)"
              strokeWidth="4"
              strokeLinecap="round"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
          <div className="how-traveller pointer-events-none absolute left-0 top-0 z-10 hidden w-16 motion-reduce:!hidden lg:block">
            <Dishu pose="wave" className="h-auto w-full" title="" />
          </div>

          <ol className="relative grid gap-6 border-l-2 border-dashed border-line pl-6 lg:grid-cols-4 lg:border-0 lg:pl-0">
            {STEPS.map(({ title, desc, Icon }, i) => (
              <li key={title} data-reveal className="how-step lg:text-center">
                <div className="flex h-[120px] items-center lg:justify-center">
                  <span className="grid h-20 w-20 place-items-center rounded-full bg-canvas ring-4 ring-mint">
                    <Icon className="how-icon h-12 w-12" />
                  </span>
                </div>
                <div className="rounded-3xl bg-surface p-5 shadow-soft">
                  <p className="text-xs font-bold uppercase tracking-[0.16em] text-leaf">
                    Step {i + 1}
                  </p>
                  <h3 className="mt-1 font-display text-lg font-bold">{title}</h3>
                  <p className="mt-2 text-sm text-muted">{desc}</p>
                </div>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </section>
  );
}
