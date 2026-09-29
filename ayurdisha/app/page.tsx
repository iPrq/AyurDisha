import Link from "next/link";

const TOOLS = [
  {
    href: "/review",
    title: "Product Review",
    desc: "Market feasibility, legal compliance and resource accessibility, each rated separately.",
  },
  {
    href: "/patent",
    title: "Patent Advisor",
    desc: "Indian Patents Act Section 3 analysis, risk indicator, prior art and IP route suggestions.",
  },
  {
    href: "/nba-abs",
    title: "NBA / ABS",
    desc: "Biodiversity Act applicability, benefit-sharing rate and fee calculation.",
  },
] as const;

export default function Home() {
  return (
    <div className="space-y-8">
      <div className="space-y-2">
        <h1 className="text-2xl font-semibold">AyurDisha</h1>
        <p className="text-neutral-600 dark:text-neutral-400">
          Evidence-backed decision support for Ayurvedic product makers. Pick a
          tool to get started.
        </p>
      </div>
      <div className="grid gap-4 sm:grid-cols-3">
        {TOOLS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="space-y-1 rounded border border-neutral-200 p-4 hover:border-green-700 dark:border-neutral-800"
          >
            <h2 className="font-medium">{t.title}</h2>
            <p className="text-sm text-neutral-600 dark:text-neutral-400">
              {t.desc}
            </p>
          </Link>
        ))}
      </div>
    </div>
  );
}
