"use client";

import { useRef } from "react";
import { BookmarkIcon, FlagIcon, GavelIcon } from "@/components/icons/SpotIcons";
import { Dishu } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";
import { drawIcons } from "@/lib/motion";
import { Accent, SectionHeading } from "./SectionHeading";

const PRINCIPLES = [
  {
    title: "Cites only retrieved evidence",
    desc: "Every finding links to a source ID you can open. A verifier strips claims that no retrieved source supports.",
    Icon: BookmarkIcon,
  },
  {
    title: "Never invents the law",
    desc: "No made-up statutes, foreign law, patent numbers or URLs. If the corpus is silent, the report says so.",
    Icon: GavelIcon,
  },
  {
    title: "Escalates instead of guessing",
    desc: "Ambiguous botanicals and thin international evidence are flagged for human review rather than silently resolved.",
    Icon: FlagIcon,
  },
];

export function TrustPrinciples() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

        const tl = gsap.timeline({
          defaults: { ease: "power3.out" },
          scrollTrigger: { trigger: root.current, start: "top 70%", once: true },
        });
        tl.from(q("[data-heading]"), { x: -30, opacity: 0, duration: 0.7, stagger: 0.08 }).from(
          q(".trust-dishu"),
          { y: 30, opacity: 0, duration: 0.6, ease: "back.out(1.6)" },
          0.3,
        );
        q(".trust-card").forEach((card, i) => {
          const at = 0.25 + i * 0.15;
          tl.from(card, { y: 30, opacity: 0, duration: 0.6 }, at);
          drawIcons(tl, card.querySelector(".trust-icon"), at + 0.1, 0.7);
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} className="mx-auto max-w-6xl px-4 py-24 sm:px-6">
      <div className="grid items-center gap-12 lg:grid-cols-[0.8fr_1.2fr]">
        <div className="space-y-6">
          <SectionHeading
            center={false}
            eyebrow="Built to be trusted"
            title={
              <>
                Decision support that <Accent>shows its work</Accent>
              </>
            }
            sub="Regulatory questions deserve answers you can check. AyurDisha is designed around three rules."
          />
          <div data-reveal className="trust-dishu w-40">
            <Dishu pose="inspect" className="h-auto w-full" />
          </div>
        </div>
        <div className="grid gap-5">
          {PRINCIPLES.map(({ title, desc, Icon }) => (
            <div
              key={title}
              data-reveal
              className="trust-card flex items-center gap-5 rounded-3xl border border-line bg-surface p-6 shadow-soft"
            >
              <Icon className="trust-icon h-14 w-14 shrink-0" />
              <div>
                <h3 className="font-display text-lg font-bold">{title}</h3>
                <p className="mt-1 text-muted">{desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
