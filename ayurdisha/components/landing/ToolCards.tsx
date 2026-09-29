"use client";

import Link from "next/link";
import { useRef } from "react";
import {
  BalanceIcon,
  CertificateIcon,
  JarIcon,
  NodesIcon,
} from "@/components/icons/SpotIcons";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";
import { drawIcons } from "@/lib/motion";
import { Accent, SectionHeading } from "./SectionHeading";

const TOOLS = [
  {
    href: "/review",
    title: "Product Review",
    desc: "Market feasibility, legal compliance and resource accessibility, each rated separately with evidence.",
    Icon: JarIcon,
  },
  {
    href: "/patent",
    title: "Patent Advisor",
    desc: "Section 3 risk indicator across 15 clauses, prior art, grant likelihood and IP route suggestions.",
    Icon: CertificateIcon,
  },
  {
    href: "/nba-abs",
    title: "NBA / ABS",
    desc: "Biological Diversity Act applicability, benefit-sharing rate and fee calculation for your resources.",
    Icon: BalanceIcon,
  },
  {
    href: "/graph",
    title: "Knowledge Graph",
    desc: "Explore herbs, compounds, classical formulations, patents and the sources behind every analysis.",
    Icon: NodesIcon,
  },
] as const;

export function ToolCards() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

        const tl = gsap.timeline({
          defaults: { ease: "power3.out" },
          scrollTrigger: { trigger: root.current, start: "top 72%", once: true },
        });
        tl.from(q("[data-heading]"), { y: 24, opacity: 0, duration: 0.7, stagger: 0.08 });
        q(".tool-card").forEach((card, i) => {
          const at = 0.35 + i * 0.12;
          tl.from(card, { y: 40, opacity: 0, duration: 0.7 }, at);
          drawIcons(tl, card.querySelector(".tool-icon"), at + 0.15);
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} id="tools" className="mx-auto max-w-6xl space-y-12 px-4 py-24 sm:px-6">
      <SectionHeading
        eyebrow="Four tools, one direction"
        title={
          <>
            Find the right <Accent>path</Accent> for your product
          </>
        }
        sub="Start with a product review, or go straight to the question that is keeping you up at night."
      />
      <div className="grid gap-5 sm:grid-cols-2 lg:grid-cols-4">
        {TOOLS.map(({ href, title, desc, Icon }) => (
          <Link
            key={href}
            href={href}
            data-reveal
            className="tool-card group flex flex-col gap-3 rounded-3xl border border-line bg-surface p-6 shadow-soft transition-transform duration-300 hover:-translate-y-1.5"
          >
            <Icon className="tool-icon mb-2 h-16 w-16 transition-transform duration-300 group-hover:-rotate-6 group-hover:scale-105" />
            <span className="font-display text-lg font-bold">{title}</span>
            <span className="flex-1 text-sm text-muted">{desc}</span>
            <span className="pt-1 text-sm font-semibold text-leaf">
              Open{" "}
              <span className="inline-block transition-transform group-hover:translate-x-1">
                →
              </span>
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}
