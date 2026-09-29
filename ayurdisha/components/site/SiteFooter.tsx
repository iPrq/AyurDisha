import Link from "next/link";
import { NAV } from "@/lib/nav";

export function SiteFooter() {
  return (
    <footer className="border-t border-line bg-surface">
      <div className="mx-auto grid max-w-6xl gap-8 px-4 py-10 sm:grid-cols-[2fr_1fr] sm:px-6">
        <div className="space-y-3">
          <p className="font-display text-lg font-extrabold">
            Ayur<span className="text-leaf-bright">Disha</span>
          </p>
          <p className="max-w-md text-sm text-muted">
            Evidence-backed direction for Ayurvedic product makers: market,
            regulatory, patent and access-and-benefit-sharing analysis, with every
            claim tied to a cited source.
          </p>
          <p className="text-xs text-muted">
            Built for Smart India Hackathon · Problem Statement 26045
          </p>
        </div>
        <nav aria-label="Tools">
          <p className="mb-3 text-sm font-semibold">Tools</p>
          <ul className="space-y-2 text-sm text-muted">
            {NAV.map((n) => (
              <li key={n.href}>
                <Link href={n.href} className="hover:text-leaf">
                  {n.label}
                </Link>
              </li>
            ))}
          </ul>
        </nav>
      </div>
      {/* Bottom padding keeps the fixed "Ask Disha" launcher clear of this line. */}
      <p className="border-t border-line px-4 pb-32 pt-4 text-center text-xs text-muted">
        Decision support only. Not legal, regulatory, or investment advice.
      </p>
    </footer>
  );
}
