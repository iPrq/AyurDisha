"use client";

import Link from "next/link";
import { useRef } from "react";
import { Dishu } from "@/components/mascot/Dishu";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

const INK = "#14261C";
const LEAF = "#6CC58C";
const SPROUT = "#8BD6A3";
const SHADE = "#2F9E5B";
const TURMERIC = "#F2A93B";
const CREAM = "#FFF8E7";
const CLAY = "#E07A50";

// Headline words; `accent` words get the leaf colour and a drawn underline.
const HEADLINE: { w: string; accent?: boolean }[] = [
  { w: "Your" },
  { w: "Ayurvedic" },
  { w: "product," },
  { w: "guided", accent: true },
  { w: "in" },
  { w: "every" },
  { w: "disha.", accent: true },
];

export function Hero() {
  const root = useRef<HTMLElement>(null);

  useGSAP(
    () => {
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(root);
        gsap.set(q("[data-reveal]"), { autoAlpha: 1 });

        const tl = gsap.timeline({ defaults: { ease: "power3.out" } });
        tl.from(q(".hero-word"), {
          yPercent: 110,
          duration: 0.9,
          stagger: 0.06,
          ease: "power4.out",
        })
          .fromTo(
            q(".hero-scribble"),
            { drawSVG: "0%" },
            { drawSVG: "100%", duration: 0.6, stagger: 0.2, ease: "power2.inOut" },
            "-=0.3",
          )
          .from(
            q(".hero-sub, .hero-cta"),
            { y: 20, opacity: 0, duration: 0.6, stagger: 0.08 },
            "-=0.8",
          )
          .from(
            q(".hero-blob"),
            {
              scale: 0.6,
              opacity: 0,
              transformOrigin: "50% 50%",
              duration: 1.1,
              ease: "expo.out",
            },
            0.2,
          )
          .from(
            q(".hero-piece"),
            {
              scale: 0,
              transformOrigin: "50% 50%",
              duration: 0.6,
              stagger: 0.08,
              ease: "back.out(1.7)",
            },
            0.5,
          )
          .from(
            q(".hero-dishu"),
            { y: -120, opacity: 0, duration: 0.9, ease: "bounce.out" },
            0.6,
          );

        // Decorations drift at different speeds as the page scrolls.
        q(".hero-deco").forEach((el) => {
          gsap.to(el, {
            y: -120 * Number(el.dataset.speed ?? 1),
            ease: "none",
            scrollTrigger: {
              trigger: root.current,
              start: "top top",
              end: "bottom top",
              scrub: true,
            },
          });
        });
        gsap.to(q(".hero-deco-spin"), {
          rotation: 360,
          transformOrigin: "50% 50%",
          duration: 18,
          repeat: -1,
          ease: "none",
        });
      });
    },
    { scope: root },
  );

  return (
    <section
      ref={root}
      className="relative overflow-hidden bg-gradient-to-b from-mint via-canvas to-canvas"
    >
      <div className="mx-auto grid max-w-6xl items-center gap-12 px-4 pb-20 pt-10 sm:px-6 lg:grid-cols-[1.05fr_1fr] lg:pt-16">
        <div className="space-y-7">
          <h1
            data-reveal
            className="font-display text-[clamp(2.6rem,6vw,4.6rem)] font-extrabold leading-[1.05] tracking-tight"
          >
            {HEADLINE.map(({ w, accent }, i) => (
              <span key={i}>
                <span className={`relative inline-block ${accent ? "text-leaf-bright" : ""}`}>
                  <span className="-mb-[0.12em] inline-block overflow-hidden pb-[0.12em] align-bottom">
                    <span className="hero-word inline-block">{w}</span>
                  </span>
                  {accent && (
                    <svg
                      aria-hidden
                      viewBox="0 0 200 20"
                      preserveAspectRatio="none"
                      className="absolute -bottom-[0.12em] left-0 h-[0.28em] w-full"
                    >
                      <path
                        className="hero-scribble"
                        d="M4 14 C 50 4, 110 4, 196 10"
                        fill="none"
                        stroke="var(--turmeric)"
                        strokeWidth="7"
                        strokeLinecap="round"
                        vectorEffect="non-scaling-stroke"
                      />
                    </svg>
                  )}
                </span>
                {i < HEADLINE.length - 1 && " "}
              </span>
            ))}
          </h1>

          <p data-reveal className="hero-sub max-w-xl text-lg text-muted">
            Market feasibility, regulatory compliance, patentability and
            access-and-benefit-sharing for Ayurvedic products, in one
            evidence-backed report where every claim points to a cited source.
          </p>

          <div data-reveal className="hero-cta flex flex-wrap gap-3">
            <Link
              href="/review"
              className="rounded-full bg-turmeric px-7 py-3.5 font-semibold text-[#14261C] shadow-soft transition-transform hover:-translate-y-0.5 hover:bg-turmeric-deep"
            >
              Review my product
            </Link>
            <Link
              href="/patent"
              className="rounded-full border-2 border-ink/80 px-7 py-3 font-semibold transition-colors hover:bg-ink hover:text-canvas"
            >
              Check patentability
            </Link>
          </div>

        </div>

        <div data-reveal className="relative mx-auto aspect-square w-full max-w-[560px]">
          <HeroArt />
          <div className="hero-dishu absolute left-1/2 top-[54%] w-[50%] -translate-x-1/2 -translate-y-1/2">
            <Dishu pose="wave" className="h-auto w-full drop-shadow-xl" />
          </div>
        </div>
      </div>
    </section>
  );
}

/** Leaf shape pointing along +x from the origin; place with a transform. */
function Leaf({
  t,
  fill = LEAF,
  w = 44,
}: {
  t: string;
  fill?: string;
  w?: number;
}) {
  const h = w * 0.24;
  return (
    <g transform={t}>
      <path
        d={`M0 0 C${w * 0.28} ${-h} ${w * 0.75} ${-h} ${w} 0 C${w * 0.75} ${h} ${w * 0.28} ${h} 0 0 Z`}
        fill={fill}
        stroke={INK}
        strokeWidth="2.5"
        strokeLinejoin="round"
      />
      <path d={`M3 0 L${w - 6} 0`} stroke={INK} strokeWidth="1.4" opacity="0.4" />
    </g>
  );
}

function HeroArt() {
  const line = {
    stroke: INK,
    strokeWidth: 3,
    strokeLinejoin: "round" as const,
    strokeLinecap: "round" as const,
  };
  return (
    <svg viewBox="0 0 560 560" className="absolute inset-0 h-full w-full" aria-hidden>
      <path
        className="hero-blob"
        d="M300 36 C420 30 530 130 520 280 C512 410 420 520 270 516 C130 512 36 420 44 280 C52 150 170 42 300 36 Z"
        fill="var(--blob)"
      />

      {/* decorations (parallax) */}
      <g className="hero-deco" data-speed="0.6">
        <circle className="hero-deco-spin" cx="72" cy="120" r="18" fill="none" stroke={TURMERIC} strokeWidth="9" strokeDasharray="70 20" />
      </g>
      <g className="hero-deco" data-speed="1.2">
        <circle cx="505" cy="190" r="12" fill="none" stroke={CLAY} strokeWidth="6" />
      </g>
      <g className="hero-deco" data-speed="0.9" fill={SHADE} opacity="0.35">
        {Array.from({ length: 16 }, (_, i) => (
          <circle key={i} cx={440 + (i % 4) * 16} cy={470 + Math.floor(i / 4) * 16} r="3" />
        ))}
      </g>
      <g className="hero-deco" data-speed="1.5">
        <path d="M40 330 L46 344 L60 350 L46 356 L40 370 L34 356 L20 350 L34 344 Z" fill={TURMERIC} stroke={INK} strokeWidth="2" strokeLinejoin="round" />
      </g>
      <g className="hero-deco" data-speed="0.8">
        <Leaf t="translate(250 40) rotate(-30)" fill={SPROUT} w={30} />
      </g>

      {/* tulsi sprig */}
      <g className="hero-piece">
        <path d="M130 440 C112 370 116 290 146 200" fill="none" stroke={SHADE} strokeWidth="5" strokeLinecap="round" />
        <Leaf t="translate(144 214) rotate(-150)" />
        <Leaf t="translate(146 212) rotate(-30)" fill={SPROUT} />
        <Leaf t="translate(128 272) rotate(-160)" fill={SPROUT} w={50} />
        <Leaf t="translate(131 270) rotate(-20)" w={50} />
        <Leaf t="translate(118 336) rotate(-165)" w={54} />
        <Leaf t="translate(120 334) rotate(-15)" fill={SPROUT} w={50} />
        <circle cx="146" cy="196" r="7" fill={CLAY} stroke={INK} strokeWidth="2.5" />
      </g>

      {/* compass rose */}
      <g className="hero-piece">
        <circle cx="440" cy="112" r="40" fill={CREAM} {...line} />
        <circle cx="440" cy="112" r="30" fill="none" stroke={INK} strokeWidth="1.2" strokeDasharray="3 5" />
        <path d="M440 78 L448 112 L440 146 L432 112 Z" fill={TURMERIC} {...line} strokeWidth={2.2} />
        <path d="M406 112 L440 104 L474 112 L440 120 Z" fill={SPROUT} {...line} strokeWidth={2.2} />
        <path d="M440 78 L448 112 L432 112 Z" fill={CLAY} {...line} strokeWidth={2.2} />
        <circle cx="440" cy="112" r="4" fill={INK} />
        <text x="440" y="70" textAnchor="middle" fontSize="13" fontWeight="800" fill={INK}>
          N
        </text>
      </g>

      {/* herbal jar */}
      <g className="hero-piece">
        <rect x="400" y="300" width="96" height="140" rx="22" fill={TURMERIC} {...line} />
        <rect x="392" y="276" width="112" height="32" rx="8" fill={SHADE} {...line} />
        <rect x="416" y="340" width="64" height="64" rx="8" fill={CREAM} {...line} strokeWidth={2.2} />
        <Leaf t="translate(430 372) rotate(-20)" w={36} />
        <path d="M412 318 L412 420" stroke="#fff" strokeWidth="6" strokeLinecap="round" opacity="0.5" />
      </g>

      {/* document with shield */}
      <g className="hero-piece">
        <g transform="rotate(-8 140 460)">
          <path d="M80 396 H176 L200 420 V520 H80 Z" fill="#fff" {...line} />
          <path d="M176 396 V420 H200" fill={CREAM} {...line} />
          <path d="M96 424 H160 M96 440 H168 M96 456 H140" stroke={INK} strokeWidth="2.5" strokeLinecap="round" opacity="0.4" />
          <path
            d="M160 452 L180 460 V476 C180 488 171 496 160 500 C149 496 140 488 140 476 V460 Z"
            fill={SHADE}
            {...line}
            strokeWidth={2.4}
          />
          <path d="M152 476 L158 482 L168 470" stroke="#fff" strokeWidth="3" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </g>
    </svg>
  );
}
