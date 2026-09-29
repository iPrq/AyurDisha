"use client";

import { useRef } from "react";
import { gsap, MOTION_OK, useGSAP } from "@/lib/gsap";

/**
 * Dishu — the AyurDisha mascot: a tulsi-leaf sprite wearing a brass compass
 * ("disha" = direction). Hand-authored SVG; every animated part carries a
 * `d-*` class so several instances can live on one page.
 *
 * The palette is fixed (not theme tokens) so the character reads the same on
 * light and dark backgrounds.
 */

export type DishuPose =
  | "wave"
  | "inspect"
  | "proud"
  | "share"
  | "connect"
  | "think"
  | "sleep"
  | "shrug"
  | "celebrate";

const INK = "#14261C";
const BODY = "#6CC58C";
const SHADE = "#2F9E5B";
const SPROUT = "#8BD6A3";
const TURMERIC = "#F2A93B";
const CREAM = "#FFF8E7";
const CLAY = "#E07A50";
const SKY = "#5B8DEF";

type Arm = { d: string; hand: [number, number] };

const ARMS = {
  downL: { d: "M52 128 Q34 146 36 164", hand: [36, 166] },
  downR: { d: "M148 128 Q166 146 164 164", hand: [164, 166] },
  waveR: { d: "M150 124 Q170 112 174 88", hand: [174, 84] },
  raiseL: { d: "M50 124 Q30 112 26 88", hand: [26, 84] },
  holdR: { d: "M150 130 Q170 136 178 124", hand: [180, 122] },
  holdL: { d: "M50 130 Q30 136 22 124", hand: [20, 122] },
  shrugL: { d: "M52 128 Q34 126 28 110", hand: [27, 106] },
  shrugR: { d: "M148 128 Q166 126 172 110", hand: [173, 106] },
  chinR: { d: "M150 130 Q146 146 124 130", hand: [121, 127] },
} satisfies Record<string, Arm>;

type Eyes = "open" | "up" | "closed" | "happy";
type Mouth = "smile" | "open" | "flat" | "o" | "wavy";

const POSES: Record<
  DishuPose,
  { l: Arm; r: Arm; eyes: Eyes; mouth: Mouth }
> = {
  wave: { l: ARMS.downL, r: ARMS.waveR, eyes: "open", mouth: "smile" },
  inspect: { l: ARMS.downL, r: ARMS.holdR, eyes: "open", mouth: "o" },
  proud: { l: ARMS.downL, r: ARMS.holdR, eyes: "happy", mouth: "smile" },
  share: { l: ARMS.holdL, r: ARMS.holdR, eyes: "open", mouth: "smile" },
  connect: { l: ARMS.downL, r: ARMS.waveR, eyes: "open", mouth: "smile" },
  think: { l: ARMS.downL, r: ARMS.chinR, eyes: "up", mouth: "flat" },
  sleep: { l: ARMS.downL, r: ARMS.downR, eyes: "closed", mouth: "o" },
  shrug: { l: ARMS.shrugL, r: ARMS.shrugR, eyes: "open", mouth: "wavy" },
  celebrate: { l: ARMS.raiseL, r: ARMS.waveR, eyes: "happy", mouth: "open" },
};

export function Dishu({
  pose = "wave",
  size = 160,
  animated = true,
  className,
  title = "Dishu, the AyurDisha tulsi mascot",
}: {
  pose?: DishuPose;
  size?: number;
  animated?: boolean;
  className?: string;
  title?: string;
}) {
  const ref = useRef<SVGSVGElement>(null);
  const p = POSES[pose];

  useGSAP(
    () => {
      if (!animated) return;
      const mm = gsap.matchMedia();
      mm.add(MOTION_OK, () => {
        const q = gsap.utils.selector(ref);
        const loop = { repeat: -1, yoyo: true, ease: "sine.inOut" } as const;

        if (p.eyes === "open" || p.eyes === "up") {
          gsap
            .timeline({
              repeat: -1,
              repeatDelay: gsap.utils.random(2.4, 4.6),
              delay: gsap.utils.random(0.5, 2),
            })
            .to(q(".d-eye"), {
              scaleY: 0.1,
              transformOrigin: "50% 50%",
              duration: 0.08,
              yoyo: true,
              repeat: 1,
            });
        }
        gsap.fromTo(
          q(".d-sprouts"),
          { rotation: -6 },
          { rotation: 6, svgOrigin: "100 30", duration: 1.4, ...loop },
        );
        gsap.to(q(".d-torso"), {
          scaleY: 1.025,
          svgOrigin: "100 192",
          duration: 1.6,
          ...loop,
        });
        if (pose === "think") {
          gsap.to(q(".d-needle"), {
            rotation: 360,
            svgOrigin: "100 148",
            duration: 1.6,
            repeat: -1,
            ease: "none",
          });
          gsap.to(q(".d-fx > *"), {
            autoAlpha: 0.2,
            stagger: 0.25,
            duration: 0.6,
            ...loop,
          });
        } else {
          gsap.fromTo(
            q(".d-needle"),
            { rotation: -12 },
            { rotation: 12, svgOrigin: "100 148", duration: 1.1, ...loop },
          );
        }
        if (pose === "wave" || pose === "connect") {
          gsap.fromTo(
            q(".d-arm-r"),
            { rotation: -8 },
            { rotation: 12, svgOrigin: "150 126", duration: 0.45, ...loop },
          );
        }
        if (pose === "celebrate") {
          gsap.to(q(".d-all"), {
            y: -8,
            duration: 0.45,
            repeat: -1,
            yoyo: true,
            ease: "power1.inOut",
          });
          gsap.to(q(".d-fx > *"), {
            scale: 0.4,
            transformOrigin: "50% 50%",
            stagger: 0.15,
            duration: 0.5,
            ...loop,
          });
        }
        if (pose === "sleep") {
          gsap.fromTo(
            q(".d-fx > *"),
            { y: 6, autoAlpha: 0 },
            {
              y: -10,
              autoAlpha: 1,
              stagger: 0.5,
              duration: 1.5,
              repeat: -1,
              ease: "sine.out",
            },
          );
        }
        if (pose === "connect") {
          gsap.to(q(".d-node"), {
            scale: 1.3,
            transformOrigin: "50% 50%",
            stagger: 0.3,
            duration: 0.7,
            ...loop,
          });
        }
      });
    },
    { scope: ref, dependencies: [pose, animated] },
  );

  return (
    <svg
      ref={ref}
      viewBox="-20 -14 240 234"
      width={size}
      height={(size * 234) / 240}
      className={className}
      role="img"
      aria-label={title}
    >
      <g className="d-all">
        <ellipse cx="100" cy="206" rx="46" ry="7" fill={INK} opacity="0.12" />

        {/* legs */}
        <g
          stroke={INK}
          strokeWidth="5"
          strokeLinecap="round"
          strokeLinejoin="round"
          fill="none"
        >
          <path d="M86 184 L84 202 L74 203" />
          <path d="M114 184 L116 202 L126 203" />
        </g>

        <g className="d-torso">
          {/* sprouts */}
          <g className="d-sprouts" stroke={INK} strokeWidth="2.5" strokeLinejoin="round">
            <path d="M100 32 L100 18" strokeLinecap="round" fill="none" />
            <path d="M100 20 C88 6 74 8 70 16 C80 24 92 24 100 20 Z" fill={SPROUT} />
            <path d="M100 20 C112 4 128 6 132 14 C122 24 108 24 100 20 Z" fill={SPROUT} />
          </g>

          {/* leaf body */}
          <path
            d="M100 30 C140 55 162 100 156 140 C150 176 126 192 100 192 C74 192 50 176 44 140 C38 100 60 55 100 30 Z"
            fill={BODY}
          />
          <path
            d="M100 30 C140 55 162 100 156 140 C150 176 126 192 100 192 Z"
            fill={SHADE}
            opacity="0.22"
          />
          <path
            d="M100 30 C140 55 162 100 156 140 C150 176 126 192 100 192 C74 192 50 176 44 140 C38 100 60 55 100 30 Z"
            fill="none"
            stroke={INK}
            strokeWidth="3"
            strokeLinejoin="round"
          />
          {/* vein */}
          <g stroke={INK} strokeWidth="2" strokeLinecap="round" opacity="0.35" fill="none">
            <path d="M100 166 L100 188" />
            <path d="M100 174 L88 166" />
            <path d="M100 180 L113 171" />
            <path d="M100 44 L100 64" />
          </g>

          <DishuEyes kind={p.eyes} />

          {/* cheeks */}
          <ellipse cx="68" cy="113" rx="7" ry="4" fill={CLAY} opacity="0.5" />
          <ellipse cx="132" cy="113" rx="7" ry="4" fill={CLAY} opacity="0.5" />

          <DishuMouth kind={p.mouth} />

          {/* compass pendant */}
          <path
            d="M84 126 L100 134 L116 126"
            stroke={INK}
            strokeWidth="1.6"
            fill="none"
            strokeLinecap="round"
          />
          <circle cx="100" cy="148" r="14" fill={TURMERIC} stroke={INK} strokeWidth="2.5" />
          <circle cx="100" cy="148" r="9.5" fill={CREAM} stroke={INK} strokeWidth="1.2" />
          <g className="d-needle">
            <path d="M100 139.5 L103.2 148 L96.8 148 Z" fill={CLAY} />
            <path d="M100 156.5 L103.2 148 L96.8 148 Z" fill={INK} />
          </g>
          <circle cx="100" cy="148" r="1.6" fill={CREAM} />
        </g>

        <DishuProp pose={pose} />

        <DishuArm arm={p.l} className="d-arm-l" />
        <DishuArm arm={p.r} className="d-arm-r" />

        <DishuFx pose={pose} />
      </g>
    </svg>
  );
}

function DishuArm({ arm, className }: { arm: Arm; className: string }) {
  return (
    <g className={className}>
      <path
        d={arm.d}
        stroke={INK}
        strokeWidth="5"
        strokeLinecap="round"
        fill="none"
      />
      <circle
        cx={arm.hand[0]}
        cy={arm.hand[1]}
        r="6.5"
        fill={BODY}
        stroke={INK}
        strokeWidth="2.5"
      />
    </g>
  );
}

function DishuEyes({ kind }: { kind: Eyes }) {
  if (kind === "closed" || kind === "happy") {
    const d =
      kind === "closed"
        ? ["M71 96 Q81 104 91 96", "M109 96 Q119 104 129 96"]
        : ["M71 100 Q81 88 91 100", "M109 100 Q119 88 129 100"];
    return (
      <g stroke={INK} strokeWidth="3" strokeLinecap="round" fill="none">
        <path d={d[0]} />
        <path d={d[1]} />
      </g>
    );
  }
  const dy = kind === "up" ? -4 : 2;
  return (
    <>
      {[81, 119].map((cx) => (
        <g key={cx} className="d-eye">
          <circle cx={cx} cy="96" r="10.5" fill="#fff" stroke={INK} strokeWidth="2.5" />
          <circle cx={cx + 1.5} cy={96 + dy} r="5.5" fill={INK} />
          <circle cx={cx + 3.5} cy={94 + dy} r="1.8" fill="#fff" />
        </g>
      ))}
    </>
  );
}

function DishuMouth({ kind }: { kind: Mouth }) {
  const stroke = {
    stroke: INK,
    strokeWidth: 2.6,
    strokeLinecap: "round" as const,
    fill: "none",
  };
  switch (kind) {
    case "open":
      return (
        <g>
          <path d="M88 112 Q100 130 112 112 Z" fill={INK} strokeLinejoin="round" />
          <ellipse cx="100" cy="120" rx="4.5" ry="2.6" fill={CLAY} />
        </g>
      );
    case "flat":
      return <path d="M93 117 L107 117" {...stroke} />;
    case "o":
      return <ellipse cx="100" cy="117" rx="3.6" ry="4.4" fill={INK} />;
    case "wavy":
      return <path d="M90 118 Q95 114 100 118 Q105 122 110 118" {...stroke} />;
    default:
      return <path d="M89 113 Q100 123 111 113" {...stroke} />;
  }
}

function DishuProp({ pose }: { pose: DishuPose }) {
  const line = {
    stroke: INK,
    strokeWidth: 2.5,
    strokeLinejoin: "round" as const,
    strokeLinecap: "round" as const,
  };
  switch (pose) {
    case "inspect":
      return (
        <g>
          {/* herbal jar */}
          <rect x="-8" y="156" width="30" height="40" rx="7" fill={TURMERIC} {...line} />
          <rect x="-11" y="148" width="36" height="11" rx="3" fill={SHADE} {...line} />
          <rect x="-2" y="167" width="18" height="16" rx="2" fill={CREAM} {...line} strokeWidth={1.6} />
          <path d="M7 180 C3 176 4 171 7 169 C10 171 11 176 7 180 Z" fill={SHADE} />
          {/* magnifier */}
          <path d="M182 118 L188 108" {...line} strokeWidth={5} />
          <circle cx="194" cy="96" r="14" fill={SKY} fillOpacity="0.25" {...line} strokeWidth={3} />
          <path d="M187 90 Q190 86 195 86" stroke="#fff" strokeWidth="2" fill="none" strokeLinecap="round" />
        </g>
      );
    case "proud":
      return (
        <g>
          <rect x="168" y="80" width="36" height="46" rx="4" fill={CREAM} {...line} />
          <rect x="164" y="74" width="44" height="9" rx="4.5" fill={TURMERIC} {...line} />
          <rect x="164" y="122" width="44" height="9" rx="4.5" fill={TURMERIC} {...line} />
          <path
            d="M186 90 L196 94 V102 C196 108 191 112 186 114 C181 112 176 108 176 102 V94 Z"
            fill={SHADE}
            {...line}
            strokeWidth={1.8}
          />
          <path d="M181 101 L185 105 L191 97" stroke="#fff" strokeWidth="2.2" fill="none" strokeLinecap="round" strokeLinejoin="round" />
        </g>
      );
    case "share":
      return (
        <g>
          <path d="M18 120 C2 116 -4 100 2 88 C16 90 24 104 18 120 Z" fill={SPROUT} {...line} />
          <path d="M17 118 C12 108 8 100 3 91" stroke={INK} strokeWidth="1.4" fill="none" opacity="0.5" />
          <circle cx="190" cy="108" r="12" fill={TURMERIC} {...line} />
          <circle cx="190" cy="108" r="7.5" fill="none" stroke={INK} strokeWidth="1.2" opacity="0.5" />
          <text x="190" y="112" textAnchor="middle" fontSize="11" fontWeight="700" fill={INK}>
            ₹
          </text>
        </g>
      );
    case "connect":
      return (
        <g>
          <g stroke={SHADE} strokeWidth="3" fill="none" strokeLinecap="round">
            <path d="M174 84 Q182 64 190 54" />
            <path d="M190 54 Q208 58 212 78" />
            <path d="M212 78 Q210 96 198 104" />
          </g>
          <circle className="d-node" cx="190" cy="54" r="7" fill={SKY} {...line} />
          <circle className="d-node" cx="212" cy="78" r="7" fill={TURMERIC} {...line} />
          <circle className="d-node" cx="198" cy="104" r="7" fill={CLAY} {...line} />
        </g>
      );
    default:
      return null;
  }
}

function DishuFx({ pose }: { pose: DishuPose }) {
  if (pose === "sleep") {
    return (
      <g className="d-fx" fill={INK} fontWeight="800" opacity="0.7">
        <text x="140" y="44" fontSize="16">z</text>
        <text x="154" y="28" fontSize="20">z</text>
        <text x="170" y="10" fontSize="24">Z</text>
      </g>
    );
  }
  if (pose === "think") {
    return (
      <g className="d-fx" fill={CREAM} stroke={INK} strokeWidth="2">
        <circle cx="146" cy="52" r="4" />
        <circle cx="158" cy="36" r="6" />
        <circle cx="176" cy="16" r="10" />
      </g>
    );
  }
  if (pose === "celebrate") {
    const star = (x: number, y: number, c: string, k: number) => (
      <path
        key={`${x}-${y}`}
        d={`M${x} ${y - 8 * k} L${x + 2.4 * k} ${y - 2.4 * k} L${x + 8 * k} ${y} L${x + 2.4 * k} ${y + 2.4 * k} L${x} ${y + 8 * k} L${x - 2.4 * k} ${y + 2.4 * k} L${x - 8 * k} ${y} L${x - 2.4 * k} ${y - 2.4 * k} Z`}
        fill={c}
        stroke={INK}
        strokeWidth="1.5"
        strokeLinejoin="round"
      />
    );
    return (
      <g className="d-fx">
        {star(10, 50, TURMERIC, 1)}
        {star(196, 40, SPROUT, 0.9)}
        {star(40, 16, CLAY, 0.7)}
        {star(168, 8, SKY, 0.7)}
      </g>
    );
  }
  return null;
}
