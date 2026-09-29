"use client";

import Link from "next/link";
import { useRef } from "react";
import { labelColor } from "@/components/knowledge-graph/labels";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";
import { Accent } from "./SectionHeading";

const CENTER = { x: 260, y: 190 };

// A small, real neighbourhood from the corpus around Turmeric.
const NODES = [
  { name: "Haridra", label: "Name", x: 96, y: 86 },
  { name: "Ayurvedic Pharmacopoeia", label: "Document", x: 270, y: 40 },
  { name: "Curcumin", label: "Compound", x: 438, y: 96 },
  { name: "Haridra Khanda", label: "Formulation", x: 92, y: 292 },
  { name: "US 5,401,504", label: "Patent", x: 430, y: 290 },
  { name: "Wound healing", label: "Category", x: 262, y: 344 },
];

export function GraphTeaser() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

        gsap
          .timeline({
            scrollTrigger: { trigger: root.current, start: "top 70%", once: true },
          })
          .from(q(".kg-copy > *"), {
            y: 30,
            opacity: 0,
            stagger: 0.1,
            duration: 0.7,
            ease: "power3.out",
          })
          .from(
            q(".kg-center"),
            { scale: 0, transformOrigin: "50% 50%", duration: 0.6, ease: "back.out(2)" },
            0.2,
          )
          .fromTo(
            q(".kg-edge"),
            { drawSVG: "0%" },
            { drawSVG: "100%", duration: 0.5, stagger: 0.08, ease: "power2.out" },
            0.5,
          )
          .from(
            q(".kg-node"),
            {
              scale: 0,
              transformOrigin: "50% 50%",
              duration: 0.5,
              stagger: 0.08,
              ease: "back.out(2)",
            },
            0.7,
          )
          .from(q(".kg-edge-flow"), { opacity: 0, duration: 0.5 }, 1.1);

        gsap.fromTo(
          q(".kg-pulse"),
          { scale: 1, opacity: 0.5, transformOrigin: "50% 50%" },
          {
            scale: 1.9,
            opacity: 0,
            duration: 2.2,
            stagger: { each: 0.4, repeat: -1 },
            ease: "power1.out",
          },
        );
        gsap.to(q(".kg-edge-flow"), {
          strokeDashoffset: -40,
          duration: 1.6,
          repeat: -1,
          ease: "none",
        });
      });
    },
    { scope: root },
  );

  return (
    <section ref={root} className="bg-mint py-24">
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 sm:px-6 lg:grid-cols-[1fr_1.1fr]">
        <div data-reveal className="kg-copy space-y-5">
          <p className="text-sm font-bold uppercase tracking-[0.18em] text-leaf">
            Knowledge graph
          </p>
          <h2 className="font-display text-[clamp(2rem,4vw,2.75rem)] font-extrabold leading-tight tracking-tight">
            See how every <Accent>herb</Accent> connects
          </h2>
          <p className="text-lg text-muted">
            Herbs, vernacular names, compounds, classical formulations, patents
            and the documents behind every analysis live in one Neo4j graph.
            Click any underlined name in a report to open its neighbourhood.
          </p>
          <Link
            href="/graph"
            className="inline-block rounded-full border-2 border-ink/80 px-6 py-3 font-semibold transition-colors hover:bg-ink hover:text-canvas"
          >
            Explore the graph
          </Link>
        </div>

        <div data-reveal className="rounded-[2rem] border border-line bg-surface p-4 shadow-soft">
          <svg viewBox="0 0 520 390" className="h-auto w-full" role="img" aria-label="Example knowledge graph around Turmeric">
            {NODES.map((n) => (
              <g key={n.name}>
                <line
                  className="kg-edge"
                  x1={CENTER.x}
                  y1={CENTER.y}
                  x2={n.x}
                  y2={n.y}
                  stroke="var(--line)"
                  strokeWidth="3"
                />
                <line
                  className="kg-edge-flow"
                  x1={CENTER.x}
                  y1={CENTER.y}
                  x2={n.x}
                  y2={n.y}
                  stroke={labelColor(n.label)}
                  strokeWidth="2"
                  strokeDasharray="6 14"
                  strokeLinecap="round"
                  opacity="0.6"
                />
              </g>
            ))}

            {NODES.map((n) => (
              <g key={n.name} className="kg-node">
                <circle className="kg-pulse" cx={n.x} cy={n.y} r="16" fill={labelColor(n.label)} />
                <circle cx={n.x} cy={n.y} r="16" fill={labelColor(n.label)} stroke="#14261C" strokeWidth="2.5" />
                <text
                  x={n.x}
                  y={n.y + 34}
                  textAnchor="middle"
                  fontSize="14"
                  fontWeight="600"
                  fill="var(--ink)"
                >
                  {n.name}
                </text>
              </g>
            ))}

            <g className="kg-center">
              <circle cx={CENTER.x} cy={CENTER.y} r="38" fill={labelColor("Herb")} stroke="#14261C" strokeWidth="3" />
              <text
                x={CENTER.x}
                y={CENTER.y + 5}
                textAnchor="middle"
                fontSize="15"
                fontWeight="800"
                fill="#fff"
              >
                Turmeric
              </text>
            </g>
          </svg>
          <div className="flex flex-wrap justify-center gap-x-4 gap-y-1 pb-2 text-xs text-muted">
            {["Herb", "Name", "Compound", "Formulation", "Patent", "Document", "Category"].map((l) => (
              <span key={l} className="flex items-center gap-1.5">
                <span className="h-2.5 w-2.5 rounded-full" style={{ backgroundColor: labelColor(l) }} />
                {l}
              </span>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
