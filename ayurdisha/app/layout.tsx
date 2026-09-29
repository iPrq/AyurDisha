import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import Link from "next/link";
import { AgentShell } from "@/components/agent/AgentShell";
import { HealthDot } from "@/components/HealthDot";
import { KnowledgeGraphProvider } from "@/components/knowledge-graph/KnowledgeGraphProvider";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AyurDisha",
  description:
    "Decision support for Ayurvedic products: market, regulatory, patent and ABS analysis.",
};

const NAV = [
  { href: "/formulation", label: "Formulation" },
  { href: "/review", label: "Product Review" },
  { href: "/patent", label: "Patent Advisor" },
  { href: "/nba-abs", label: "NBA / ABS" },
  { href: "/graph", label: "Knowledge Graph" },
] as const;

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      className={`${geistSans.variable} ${geistMono.variable} h-full antialiased`}
    >
      <body className="flex min-h-full flex-col font-sans">
        <KnowledgeGraphProvider>
          <AgentShell>
            <header className="border-b border-neutral-200 dark:border-neutral-800">
              <div className="mx-auto flex max-w-4xl flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3">
                <Link href="/" className="font-semibold text-green-800 dark:text-green-400">
                  AyurDisha
                </Link>
                <nav className="flex gap-4 text-sm">
                  {NAV.map((n) => (
                    <Link key={n.href} href={n.href} className="hover:underline">
                      {n.label}
                    </Link>
                  ))}
                </nav>
                <div className="ml-auto">
                  <HealthDot />
                </div>
              </div>
            </header>
            <main className="mx-auto w-full max-w-4xl flex-1 px-4 py-8">
              {children}
            </main>
            <footer className="border-t border-neutral-200 py-4 text-center text-xs text-neutral-500 dark:border-neutral-800">
              Decision support only. Not legal, regulatory, or investment advice.
            </footer>
          </AgentShell>
        </KnowledgeGraphProvider>
      </body>
    </html>
  );
}
