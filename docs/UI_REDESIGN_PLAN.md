# AyurDisha UI Redesign Plan — "Hoomi-style, but Ayurvedic green"

**Goal:** turn the current plain dark Next.js shell into a landing-page-led product that stands out at SIH (PS 26045) — bold illustrated hero, friendly mascot, GSAP motion — without breaking the four working tools (Product Review, Patent Advisor, NBA / ABS, Knowledge Graph).

**Reference:** [Hoomi Insurance Landing Page (Dribbble)](https://dribbble.com/shots/16616409-Hoomi-Insurance-Landing-Page). We borrow its *style language*, not its assets.

---

## 1. What we take from Hoomi (and how it becomes AyurDisha)

| Hoomi trait | AyurDisha translation |
|---|---|
| Soft lavender page background with big pastel blob behind the hero art | Soft **sage/mint** background (`#E9F3EA`) with a leaf-shaped blob (`#CFE8D3`) |
| Huge bold headline, one or two words in a bright accent colour ("Insurance … **You**") | "Your Ayurvedic Product, **Guided** in Every **Disha**" — accent words in leaf green |
| Flat line-art illustration: thick black outlines + flat fills (yellow / blue) | Thick ink outlines (`#14261C`) + flat fills in leaf green, **turmeric** yellow, clay orange |
| Orange pill CTA button | **Turmeric** pill CTA (`#F2A93B`) with ink text (white-on-turmeric fails contrast) |
| Floating white stat cards around the hero ("25 million+ customers" + avatars) | Floating cards with **real** facts: "3 Acts indexed", "15 Section 3 clauses checked", "Every claim cited" |
| Little decorative shapes: donut rings, dots, sparkles | Donut rings, dots, small tulsi leaves, a compass rose — all animated |
| Row of 4 white service cards with coloured icon tiles | 4 tool cards: Product Review, Patent Advisor, NBA / ABS, Knowledge Graph |
| Split section "Get the right protection…" with stat cards | "Know your risk **before** you file" with a mock result card (risk gauge + 3(d)/3(e)/3(p) chips) |
| Friendly, rounded, generous whitespace | Same — rounded-2xl/3xl cards, soft shadows, 1200px container |

---

## 2. Design system

### 2.1 Colour tokens (Tailwind v4 `@theme` in `app/globals.css`)

| Token | Light | Dark | Use |
|---|---|---|---|
| `--color-canvas` | `#F6FAF4` | `#0D1812` | page background |
| `--color-mint` | `#E9F3EA` | `#12211A` | section bands |
| `--color-blob` | `#CFE8D3` | `#1A3326` | hero blob, icon tiles |
| `--color-surface` | `#FFFFFF` | `#14231A` | cards |
| `--color-line` | `#DCE8DD` | `#22382A` | borders |
| `--color-ink` | `#14261C` | `#E8F0E9` | text, illustration outlines |
| `--color-muted` | `#4F6356` | `#9DB3A4` | secondary text |
| `--color-leaf-700` | `#1E6B43` | `#5CC98A` | primary, links (AA on its bg) |
| `--color-leaf-500` | `#2F9E5B` | `#5CC98A` | headline accent words (large text only) |
| `--color-turmeric` | `#F2A93B` | `#F2A93B` | CTA fill (ink text on top) |
| `--color-clay` | `#D0643A` | `#E07A50` | decorative, "high risk" |
| `--color-sky` | `#5B8DEF` | `#7EA6F5` | knowledge-graph accent, info |

Risk semantics: low = leaf, medium = turmeric, high = clay, human-review = sky. Always pair colour with a text label.

**Theme:** light-first (matches Hoomi); keep a proper dark theme via `prefers-color-scheme` so current dark users aren't blinded.

### 2.2 Type
- Display: **Plus Jakarta Sans** 700/800 via `next/font/google` (`--font-display`) — geometric and friendly like Hoomi's.
- Body/UI: keep **Geist** (already wired), Geist Mono for source IDs.
- Scale: hero 56–72px (clamp), h2 40px, h3 22px, body 16–18px.

### 2.3 Shape & depth
- Radius: cards `rounded-3xl`, inputs/buttons `rounded-full` / `rounded-xl`.
- Shadow: one soft token `--shadow-soft: 0 12px 40px -12px rgb(20 38 28 / 0.18)`.
- Illustration stroke: 2.5px ink, round caps/joins.

---

## 3. Mascot — **Dishu**, the Tulsi compass sprite

*"Disha" = direction. Dishu is a tulsi leaf that carries a compass and points makers the right way.*

- **Body:** a plump tulsi leaf (teardrop), leaf-500 fill, ink outline, one centre vein line.
- **Head:** two small sprout leaves on top (they sway).
- **Face:** big round eyes with white highlight, small smile, clay blush cheeks.
- **Limbs:** simple line-art arms and stubby legs.
- **Signature prop:** a turmeric/brass **compass pendant** on the chest; the needle is its own group so it can spin.
- **Style:** same line art as the hero — flat fills, 2.5px ink stroke, no gradients.

**Poses / accessories (one base SVG + swappable prop groups):**

| Where | Pose | Prop |
|---|---|---|
| Hero | waving | compass |
| Product Review | inspecting | magnifying glass over a herbal jar |
| Patent Advisor | proud | scroll with a shield ✓ |
| NBA / ABS | sharing | leaf in one hand, coin in the other (benefit sharing) |
| Knowledge Graph | connecting | vine linking three dots |
| Loading (long LLM calls) | thinking | compass needle spinning |
| Error / backend offline | sleepy / wilted | "zzz" |
| Empty result | shrug | — |

**SVG structure (required for GSAP):** `#dishu-root > #shadow, #legs, #body, #vein, #sprout-l, #sprout-r, #eye-l, #eye-r, #lid-l, #lid-r, #cheeks, #mouth, #arm-l, #arm-r, #compass, #needle, #prop-*`. All transform origins set with `transform-box: fill-box`.

**Idle loop:** blink every 3–5s (random), sprouts sway ±6°, body breathes (scaleY 1→1.03), needle wobbles ±10°.

---

## 4. Information architecture & layout changes

The current root layout caps everything at `max-w-4xl`, so a full-bleed landing page is impossible. Split it with route groups (URLs don't change):

```
app/
  layout.tsx                 ← html/body, fonts, providers, <SiteHeader/>, <SiteFooter/>, NO width cap
  (marketing)/page.tsx       ← new landing page (moved from app/page.tsx)
  (tools)/layout.tsx         ← container max-w-6xl + tool page chrome (mascot + page hero)
  (tools)/review/page.tsx
  (tools)/patent/page.tsx
  (tools)/nba-abs/page.tsx
  (tools)/graph/page.tsx
```

New components:

```
components/
  site/SiteHeader.tsx        ← client: active link via usePathname, shrink-on-scroll, mobile menu
  site/SiteFooter.tsx
  mascot/Dishu.tsx           ← client: inline SVG + idle animation, props: pose, prop, size
  landing/Hero.tsx
  landing/SourcesStrip.tsx
  landing/ToolCards.tsx
  landing/HowItWorks.tsx
  landing/RiskShowcase.tsx
  landing/GraphTeaser.tsx
  landing/TrustPrinciples.tsx
  landing/Faq.tsx
  landing/CtaBand.tsx
  motion/Reveal.tsx          ← generic ScrollTrigger fade/rise wrapper
  motion/Counter.tsx
lib/gsap.ts                  ← registers plugins once, exports gsap + useGSAP
```

---

## 5. Landing page — section by section

1. **Header** — logo (mini Dishu + wordmark), links with an active pill, `HealthDot` restyled as a chip, turmeric "Start analysis" pill. Shrinks and gains a blur backdrop after 40px scroll.
2. **Hero** (two columns, stacks on mobile)
   - Tag pill: `SIH 2026 · PS 26045` (**confirm the official PS title/number**).
   - Headline: "Your Ayurvedic Product, **Guided** in Every **Disha**".
   - Sub: "Market feasibility, regulatory compliance, patentability and ABS — one evidence-backed report, every claim cited."
   - CTAs: turmeric "Review my product" → `/review`; ghost "Check patentability" → `/patent`.
   - Right: leaf blob, Dishu waving, herbal jar, tulsi/ashwagandha/neem line art, a document with a shield check. Floating cards: "3 Acts indexed", "15 Section 3 clauses", "Cited evidence only".
3. **Sources strip** — "Grounded in": Patents Act 1970 · Biological Diversity Act 2002 · Drugs & Cosmetics Act 1940 (Ch. IVA) as muted pills (only list what's actually in the corpus).
4. **Tool cards** — "Find the right path for your product": four white cards with mint icon tiles, hover lift, "Open →".
5. **How it works** — four steps along a curvy SVG vine that **draws on scroll**: Describe or upload PDF → Normalise botanicals → Retrieve statutes & evidence → Verified, cited report. Dishu travels along the path (MotionPath).
6. **Risk showcase** — "Know your risk **before** you file": left copy, right a mock Patent Advisor result card. Gauge sweeps, 3(d)/3(e)/3(p) chips pop in, counter ticks. Label clearly as an **example**.
7. **Graph teaser** — small animated node network (pure SVG, not the heavy force-graph lib) → `/graph`.
8. **Trust principles** — three cards straight from the backend's safety rules: "Never invents statutes or patent numbers", "Ambiguous botanicals escalate — never silently guessed", "Human review flagged when evidence is thin".
9. **FAQ** — 5 questions (Is this legal advice? What data is used? Can I upload a PDF? What is ABS? What does the risk score mean?).
10. **CTA band** — mint band, Dishu celebrating, "Ready to find your direction?" + CTA.
11. **Footer** — links, disclaimer (keep the current text), SIH team credit.

---

## 6. GSAP motion spec

**Packages:** `gsap` + `@gsap/react`. As of GSAP 3.13 every plugin (ScrollTrigger, SplitText, DrawSVG, MotionPath) is free and ships in the `gsap` package.

**Rules**
- Register plugins once in `lib/gsap.ts` (`"use client"`), import from there only.
- Every animated component is a small client island using `useGSAP(() => …, { scope: ref })` — automatic cleanup on unmount/route change.
- Wrap everything in `gsap.matchMedia()` with `(prefers-reduced-motion: no-preference)`; reduced-motion users get the final state instantly.
- Prevent flash of unstyled content: elements start with a `.will-animate { visibility: hidden }` class and animate with `autoAlpha`; a `<noscript>` style reveals them.
- Animate only `transform` and `opacity`. No layout properties.
- `ScrollTrigger.refresh()` after `document.fonts.ready`.

**Timeline**

| Element | Animation | Ease / timing |
|---|---|---|
| Hero headline | Words pre-split in JSX (each in an overflow mask; avoids SplitText rewriting React-owned DOM), `yPercent: 110 → 0`, stagger 0.06 | `power4.out`, 0.9s |
| Accent words | green underline scribble draws in (DrawSVG) after headline | 0.6s |
| Hero art | blob scales from 0.6, then pieces pop (`scale 0 → 1`) with stagger | `back.out(1.7)` |
| Dishu | drops in, squash & stretch, waves twice, then idle loop | — |
| Floating cards | enter from sides, then infinite `y: ±8` yoyo at different durations | `sine.inOut` |
| Decorative shapes | parallax on scroll (`y` at different speeds, `scrub: true`) | — |
| Header | shrink + backdrop blur toggled by ScrollTrigger | 0.3s |
| Tool cards | `ScrollTrigger.batch` rise + fade, stagger 0.1; hover lift via CSS | `power3.out` |
| How it works | vine path `drawSVG 0% → 100%` scrubbed; step cards reveal as the path reaches them; Dishu on MotionPath | scrub 0.6 |
| Risk showcase | gauge arc drawSVG, needle rotate, chips stagger, numbers count up | on enter, once |
| Graph teaser | nodes breathe, edges pulse | infinite, subtle |
| CTA band | Dishu jumps, confetti leaves burst | on enter |

**Tool-page motion (keep it calm — these are work screens)**
- Page hero: title + small Dishu (page pose) fade/rise.
- On submit: form collapses slightly, **loading panel** shows Dishu with spinning needle plus pipeline stage labels (Parsing input → Normalising botanicals → Retrieving evidence → Scoring → Verifying). These are *illustrative stages cycled on a timer*, not real progress — don't show a percentage.
- On result: sections stagger in (0.08s), badges pop, risk gauge sweeps.
- Error / backend offline: sleepy Dishu + message.

---

## 7. Tool pages reskin (cheap, high leverage)

All four pages build on primitives in `components/ui.tsx` (`inputClass`, `Field`, `SubmitButton`, `ErrorBanner`, `Badge`, `Section`, `FindingList`, `Sources`, `PdfUpload`, …). Restyle **those** with the new tokens and every page updates at once:

- `inputClass` → white surface, `rounded-xl`, line border, leaf-700 focus ring.
- `SubmitButton` → turmeric pill + spinner.
- `Section` → white `rounded-3xl` card with shadow-soft and an icon tile.
- `Badge` → map risk/status values to leaf/turmeric/clay/sky pills.
- `PdfUpload` → dashed mint dropzone with Dishu holding a document.
- Add a `PageHero` (title, one-line description, Dishu pose) used by `(tools)/layout.tsx` or each page.

Don't change request/response logic in `lib/api.ts` / `lib/types.ts`.

---

## 8. Delivery phases

| Phase | Scope | Done when |
|---|---|---|
| 0. Prep | Read `node_modules/next/dist/docs/` (Next 16 has breaking changes); install `gsap @gsap/react`; add fonts | `npm run build` passes |
| 1. Tokens & shell | `globals.css` tokens (light + dark), route-group split, `SiteHeader` (active link, mobile menu), `SiteFooter` | All 4 tools still work at the same URLs |
| 2. Mascot | `Dishu.tsx` with all groups, poses, idle loop, reduced-motion fallback | Renders crisp at 48px and 360px, both themes |
| 3. Landing (static) | All sections, responsive at 375 / 768 / 1280 / 1440, no animation yet | Looks right with JS off |
| 4. Landing motion | GSAP per §6 | 60fps scroll in Chrome devtools, no CLS, reduced motion honoured |
| 5. Tool reskin | `ui.tsx` primitives, `PageHero`, loading/error/empty mascot states | Real end-to-end run on each tool with the backend up |
| 6. Polish | Lighthouse ≥ 90 perf / 100 a11y on `/`, focus states, alt text, README update | Checklist below green |

**QA checklist:** keyboard nav through the whole landing page · visible focus rings · contrast AA · `prefers-reduced-motion` · dark mode · no horizontal scroll at 375px · backend-offline state · long result lists · Lighthouse.

---

## 9. Risks & guardrails

- **Honesty in marketing copy:** stats must be real (Acts in the corpus, 15 Section 3 clauses). No fake user counts or testimonials. Mock result card is labelled "Example".
- **Not legal advice:** keep the disclaimer in the footer and near the risk showcase.
- **Illustration quality:** hand-coded SVG people look amateur. Build the hero from objects (mascot, herbs, jar, document, compass) which SVG does well. If you want Hoomi-style *people*, generate them separately (see the illustration prompt in `UI_REDESIGN_CLAUDE_PROMPT.md`) and export as SVG.
- **Bundle size:** GSAP ≈ 25–45 KB gz with plugins; load only on client islands. Keep `react-force-graph-2d` off the landing page.
- **Next 16:** verify any API (route groups, `LayoutProps`, `next/font`, metadata) against the bundled docs before using it.
