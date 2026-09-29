# Claude prompt — AyurDisha UI redesign

Paste everything inside the fence below into Claude Code, run from `C:\apna\AyurDisha`.
Fill in the `[PS 26045 official title]` placeholder first.

```text
You are redesigning the frontend of AyurDisha, our Smart India Hackathon project
(SIH 2026, Problem Statement 26045: "[PS 26045 official title]").

AyurDisha is evidence-backed decision support for Ayurvedic product makers. A FastAPI
backend (app/) exposes four tools that the Next.js frontend (ayurdisha/) already calls
through a proxy route at ayurdisha/app/api/backend/[...path]/route.ts:
  - Product Review  (/review)  – market feasibility, legal compliance, resource accessibility
  - Patent Advisor  (/patent)  – Indian Patents Act Section 3 risk indicator, prior art, IP routes
  - NBA / ABS       (/nba-abs) – Biological Diversity Act applicability, benefit-sharing fee
  - Knowledge Graph (/graph)   – Neo4j explorer (react-force-graph-2d)
It is decision support only, NOT legal advice.

The full design spec is in docs/UI_REDESIGN_PLAN.md. Read it completely before starting;
it is the source of truth for colours, type, mascot, sections, motion and phases.

## Before writing code
1. Read ayurdisha/AGENTS.md. This is Next.js 16 with breaking changes: check the relevant
   guides in ayurdisha/node_modules/next/dist/docs/ before using route groups, layouts,
   next/font, metadata or client/server component APIs.
2. Read ayurdisha/app/layout.tsx, app/page.tsx, app/globals.css, components/ui.tsx,
   lib/api.ts and each tool page so you understand what already exists.
3. Do NOT change request/response behaviour in lib/api.ts, lib/types.ts or the proxy route.

## Visual direction
Follow the style language of the Dribbble shot "Hoomi Insurance Landing Page"
(https://dribbble.com/shots/16616409-Hoomi-Insurance-Landing-Page), recoloured to Ayurvedic green:
- soft sage/mint page background with a big pastel leaf-shaped blob behind the hero art
- huge bold geometric headline with 1–2 accent words in leaf green
- flat line-art illustrations: thick ink outlines (2.5px, round caps) + flat fills in
  leaf green, turmeric yellow and clay orange, no gradients
- turmeric pill CTA with ink-coloured text
- small floating white stat cards around the hero, gently bobbing
- decorative donut rings, dots, sparkles and tiny tulsi leaves
- a row of white rounded service cards with coloured icon tiles
- generous whitespace, rounded-3xl cards, one soft shadow
Use the exact tokens from section 2 of the plan (Tailwind v4 @theme in globals.css), light-first
with a real dark theme. Fonts: Plus Jakarta Sans (display, via next/font/google) + existing Geist.
Copy the style only. Do not copy Hoomi's assets or illustrations.

## Mascot: "Dishu", the tulsi compass sprite
Build components/mascot/Dishu.tsx as a hand-authored inline SVG ("use client"):
- a plump tulsi-leaf body (teardrop, leaf green fill, ink outline, centre vein line)
- two small sprout leaves on top of the head
- big round eyes with white highlights, separate eyelid shapes for blinking, small smile,
  clay-coloured blush cheeks
- simple line-art arms and stubby legs
- a turmeric/brass compass pendant on its chest whose needle is a separate group
  ("Disha" means direction; Dishu points makers the right way)
- same line-art style as the rest of the illustrations
Every part must be its own <g> with an id (dishu-shadow, legs, body, vein, sprout-l, sprout-r,
eye-l, eye-r, lid-l, lid-r, cheeks, mouth, arm-l, arm-r, compass, needle, prop-*) and
transform-box: fill-box so GSAP can animate it.
Props: size, pose ("wave" | "inspect" | "proud" | "share" | "connect" | "think" | "sleep" |
"shrug" | "celebrate"), prop accessory (compass, magnifier+jar, scroll+shield, leaf+coin, vine,
zzz), animated (boolean). Idle loop: random blink every 3–5s, sprouts sway ±6°, subtle breathing,
needle wobble; in "think" the needle spins. Respect prefers-reduced-motion.
Make it look good at 48px (header logo) and at 360px (hero). Add role="img" and an aria-label.

## Layout restructure
Move to route groups so URLs stay the same:
  app/layout.tsx (html/body, fonts, providers, SiteHeader, SiteFooter, no width cap)
  app/(marketing)/page.tsx (new landing page)
  app/(tools)/layout.tsx (max-w-6xl container) + review, patent, nba-abs, graph moved inside
Keep KnowledgeGraphProvider and HealthDot working. SiteHeader is a client component with an active
link pill (usePathname), shrink + backdrop blur on scroll, and a mobile menu.

## Landing page sections
Build all sections from section 5 of the plan, in order: Hero, Sources strip, Tool cards,
How it works, Risk showcase, Graph teaser, Trust principles, FAQ, CTA band, Footer.
Copy rules:
- Only use true facts. The corpus has the Patents Act 1970, Biological Diversity Act 2002 and
  Drugs & Cosmetics Act 1940 (Ch. IVA); the Patent Advisor covers 15 Section 3 clauses. Verify
  these numbers against app/ before using them. No invented user counts, testimonials or logos.
- The risk showcase card is a mock and must be labelled "Example".
- Trust principles come from docs/BACKEND_GUIDE.md safety rules.
- Keep the "Decision support only. Not legal, regulatory, or investment advice." disclaimer.
Build the hero illustration from objects SVG draws well (Dishu, leaf blob, herbal jar, tulsi /
ashwagandha / neem line art, a document with a shield check, compass rose). No hand-drawn people.

## GSAP
Install gsap and @gsap/react. All plugins (ScrollTrigger, SplitText, DrawSVGPlugin,
MotionPathPlugin) ship free in the gsap package. Create lib/gsap.ts ("use client") that registers
plugins once. Rules:
- animation lives in small client islands; landing sections stay server components where possible
- useGSAP(() => {...}, { scope: ref }) everywhere so it cleans up on navigation
- gsap.matchMedia() with (prefers-reduced-motion: no-preference); otherwise show final state
- no FOUC: start hidden with a .will-animate class, animate autoAlpha; add a <noscript> override
- animate only transform/opacity; ScrollTrigger.refresh() after document.fonts.ready
Implement the motion table in section 6 of the plan: SplitText headline, DrawSVG scribble under
accent words, hero pop-in with back.out, Dishu entrance + wave + idle, bobbing stat cards,
scroll-parallax decorations, ScrollTrigger.batch card reveals, scroll-scrubbed vine path with Dishu
on a MotionPath in "How it works", gauge sweep + counters in the risk showcase, subtle graph
teaser pulses, CTA confetti leaves.

## Tool pages
Restyle the primitives in components/ui.tsx (inputClass, Field, SubmitButton, ErrorBanner, Badge,
Section, FindingList, Sources, PdfUpload, DocumentStatus...) with the new tokens so all four pages
update together. Badge colours: low = leaf, medium = turmeric, high = clay, human review = sky,
always with a text label. Add a PageHero (title, one-line description, Dishu pose per page: review
= inspect, patent = proud, nba-abs = share, graph = connect). Add:
- a loading panel with Dishu "think" plus illustrative pipeline stage labels cycled on a timer
  (Parsing input → Normalising botanicals → Retrieving evidence → Scoring → Verifying). Requests
  can take minutes. Do not show a fake percentage.
- result sections that stagger in; a sleepy Dishu for errors / backend offline; shrug for empty.
Keep motion on tool pages calm.

## Work in phases, and check each one before moving on
0 prep → 1 tokens & shell → 2 mascot → 3 static landing → 4 landing motion → 5 tool reskin →
6 polish (see section 8 of the plan). After each phase, from ayurdisha/:
  npm run lint && npm run build
then run `npm run dev` and look at the result in the browser at 375, 768 and 1440 px, in light and
dark, and with reduced motion on. Confirm /review, /patent, /nba-abs and /graph still submit
correctly (start the backend with `uv run uvicorn main:app --reload` from app/ if available).
Report what you checked and anything you could not verify. Don't commit unless I ask.
```

---

## Optional: illustration-generator prompt (for Hoomi-style people)

Claude-authored SVG is great for the mascot and objects but weak at human figures. If you want
people in the hero like Hoomi has, generate them separately with this, vectorise or export as SVG,
and drop it into `ayurdisha/public/illustrations/`:

```text
Flat vector illustration for a modern SaaS landing page hero, thick uniform black outlines,
flat colour fills only (sage green #CFE8D3, leaf green #2F9E5B, turmeric yellow #F2A93B,
clay orange #D0643A, off-white), no gradients, no shadows, no text.
Scene: a young Indian woman entrepreneur proudly holding an amber herbal product jar, and an
older researcher in a kurta holding a clipboard with a green check mark, standing among
oversized tulsi leaves, ashwagandha roots, neem sprigs, a brass mortar and pestle, and a
legal document with a shield icon. Next to them, a small cute mascot: a plump tulsi-leaf
character with big round eyes, blush cheeks, two sprout leaves on its head and a brass compass
pendant, waving. Friendly, optimistic, bold, playful composition on a transparent background,
style similar to contemporary Dribbble landing page line-art illustrations.
```
