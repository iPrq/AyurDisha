/**
 * Lineal-colour spot icons (ink outline + flat fills), drawn to match the
 * Dishu mascot. Every shape carries the `si` class so GSAP can draw the
 * outline in and then fade the fill (see `drawIcons` in lib/motion.ts).
 */

const INK = "#14261C";
const LEAF = "#6CC58C";
const SHADE = "#2F9E5B";
const TURMERIC = "#F2A93B";
const CREAM = "#FFF8E7";
const CLAY = "#E07A50";
const SKY = "#BFD3FB";
const WHITE = "#FFFFFF";

type IconProps = { className?: string };

const s = (fill = "none", extra: Record<string, unknown> = {}) => ({
  className: "si",
  fill,
  stroke: INK,
  strokeWidth: 2.5,
  strokeLinecap: "round" as const,
  strokeLinejoin: "round" as const,
  ...extra,
});

function Svg({ className, children }: IconProps & { children: React.ReactNode }) {
  return (
    <svg viewBox="0 0 64 64" className={className} aria-hidden>
      {children}
    </svg>
  );
}

/** Product Review: herbal jar with a leaf label. */
export function JarIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="14" y="22" width="36" height="35" rx="8" {...s(TURMERIC)} />
      <rect x="11" y="12" width="42" height="11" rx="3" {...s(SHADE)} />
      <rect x="21" y="30" width="22" height="18" rx="2" {...s(CREAM)} />
      <path d="M27 43 C27 36 32 33 37 34 C37 40 33 43 27 43 Z" {...s(LEAF, { strokeWidth: 2 })} />
      <path d="M27 43 L34 37" {...s("none", { strokeWidth: 1.6 })} />
      <path d="M19 27 V50" {...s("none", { stroke: WHITE, strokeWidth: 3, opacity: 0.7 })} />
    </Svg>
  );
}

/** Patent Advisor: certificate with a seal. */
export function CertificateIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="9" y="8" width="38" height="46" rx="3" {...s(CREAM)} />
      <path d="M16 18 H40 M16 25 H40 M16 32 H30" {...s()} />
      <path d="M39 50 L36 60 L42 57 L47 60 L46 50" {...s(CLAY)} />
      <circle cx="43" cy="45" r="10" {...s(CLAY)} />
      <path d="M38.5 45 L42 48.5 L48 42" {...s("none", { stroke: WHITE, strokeWidth: 3 })} />
    </Svg>
  );
}

/** NBA / ABS: balance with a leaf and a coin (benefit sharing). */
export function BalanceIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M32 14 V52 M21 55 H43 M10 20 H54" {...s()} />
      <path d="M15 20 L8 37 M15 20 L22 37 M49 20 L42 37 M49 20 L56 37" {...s("none", { strokeWidth: 1.8 })} />
      <path d="M6 37 H24 C24 44 6 44 6 37 Z" {...s(TURMERIC)} />
      <path d="M40 37 H58 C58 44 40 44 40 37 Z" {...s(TURMERIC)} />
      <path d="M10 35 C10 28 15 26 20 27 C20 32 16 35 10 35 Z" {...s(LEAF, { strokeWidth: 2 })} />
      <circle cx="49" cy="32" r="4.5" {...s(CREAM, { strokeWidth: 2 })} />
      <circle cx="32" cy="13" r="3.5" {...s(CLAY)} />
    </Svg>
  );
}

/** Knowledge Graph: connected nodes. */
export function NodesIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M17 19 L46 16 M17 19 L22 48 M46 16 L47 45 M22 48 L47 45 M17 19 L47 45" {...s("none", { strokeWidth: 2 })} />
      <circle cx="17" cy="19" r="8" {...s(SKY)} />
      <circle cx="46" cy="16" r="6.5" {...s(TURMERIC)} />
      <circle cx="22" cy="48" r="6.5" {...s(CLAY)} />
      <circle cx="47" cy="45" r="9" {...s(LEAF)} />
    </Svg>
  );
}

/** Step 1: document with an upload badge. */
export function UploadDocIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M13 7 H37 L49 19 V56 H13 Z" {...s(WHITE)} />
      <path d="M37 7 V19 H49" {...s(CREAM)} />
      <path d="M20 29 H40 M20 36 H34" {...s()} />
      <circle cx="44" cy="48" r="10" {...s(LEAF)} />
      <path d="M44 53 V43 M40 47 L44 43 L48 47" {...s("none", { stroke: WHITE, strokeWidth: 2.8 })} />
    </Svg>
  );
}

/** Step 2: leaf with a name tag. */
export function LeafTagIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M9 51 C9 27 25 11 51 11 C51 35 35 53 9 51 Z" {...s(LEAF)} />
      <path d="M9 51 L38 22 M22 38 L22 28 M29 31 L38 31" {...s("none", { strokeWidth: 1.8 })} />
      <path d="M38 22 C40 30 38 38 36 42" {...s("none", { strokeWidth: 1.6 })} />
      <path d="M38 41 H51 L58 48 L51 55 H38 Z" {...s(TURMERIC)} />
      <circle cx="43" cy="48" r="1.8" fill={INK} className="si" />
    </Svg>
  );
}

/** Step 3: open book under a magnifier. */
export function BookSearchIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M5 15 C13 11 23 11 31 17 V52 C23 46 13 46 5 50 Z" {...s(CREAM)} />
      <path d="M57 15 C49 11 39 11 31 17 V52 C39 46 49 46 57 50 Z" {...s(WHITE)} />
      <path d="M10 23 C15 21 21 21 26 24 M10 30 C15 28 21 28 26 31" {...s("none", { strokeWidth: 1.8 })} />
      <path d="M52 43 L59 50" {...s("none", { strokeWidth: 5 })} />
      <circle cx="45" cy="36" r="9" {...s(SKY)} />
    </Svg>
  );
}

/** Step 4: clipboard with a check. */
export function ClipboardIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="11" y="10" width="42" height="49" rx="5" {...s(TURMERIC)} />
      <rect x="17" y="17" width="30" height="36" rx="2" {...s(WHITE)} />
      <rect x="23" y="6" width="18" height="9" rx="3" {...s(SHADE)} />
      <path d="M23 35 L30 42 L42 27" {...s("none", { stroke: SHADE, strokeWidth: 4 })} />
    </Svg>
  );
}

/** Trust 1: book with a bookmark (cited sources). */
export function BookmarkIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <path d="M14 8 H48 V56 H14 Z" {...s(LEAF)} />
      <path d="M48 12 H53 V58 H18 V56" {...s(CREAM)} />
      <path d="M20 8 V56" {...s("none", { strokeWidth: 2 })} />
      <path d="M26 34 H42 M26 41 H38" {...s("none", { stroke: CREAM, strokeWidth: 2.4 })} />
      <path d="M34 8 V26 L38.5 22 L43 26 V8" {...s(CLAY)} />
    </Svg>
  );
}

/** Trust 2: gavel (the law). */
export function GavelIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <rect x="28" y="47" width="28" height="8" rx="2" {...s(CLAY)} />
      <g transform="rotate(-40 30 28)">
        <rect x="27" y="22" width="6" height="30" rx="3" {...s(TURMERIC)} />
        <rect x="15" y="10" width="30" height="13" rx="3" {...s(SHADE)} />
        <path d="M21 10 V23 M39 10 V23" {...s("none", { strokeWidth: 1.8 })} />
      </g>
    </Svg>
  );
}

/** Trust 3: flag (escalate for review). */
export function FlagIcon({ className }: IconProps) {
  return (
    <Svg className={className}>
      <ellipse cx="17" cy="57" rx="9" ry="3" {...s(CREAM, { strokeWidth: 2 })} />
      <path d="M17 57 V8" {...s("none", { strokeWidth: 3 })} />
      <path d="M17 10 C29 4 37 16 51 10 V32 C37 38 29 26 17 32 Z" {...s(CLAY)} />
      <path d="M30 17 V24 M30 28 V28.5" {...s("none", { stroke: WHITE, strokeWidth: 3 })} />
    </Svg>
  );
}
