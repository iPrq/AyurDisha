import type { Metadata } from "next";
import {
  Geist,
  Geist_Mono,
  Noto_Sans_Devanagari,
  Plus_Jakarta_Sans,
} from "next/font/google";
import { AgentShell } from "@/components/agent/AgentShell";
import { KnowledgeGraphProvider } from "@/components/knowledge-graph/KnowledgeGraphProvider";
import { SiteFooter } from "@/components/site/SiteFooter";
import { SiteHeader } from "@/components/site/SiteHeader";
import { SourceScopeProvider } from "@/components/site/SourceScope";
import "./globals.css";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

const jakarta = Plus_Jakarta_Sans({
  variable: "--font-jakarta",
  subsets: ["latin"],
  weight: ["600", "700", "800"],
});

const devanagari = Noto_Sans_Devanagari({
  variable: "--font-noto-devanagari",
  subsets: ["devanagari"],
  weight: ["500"],
});

export const metadata: Metadata = {
  title: "AyurDisha",
  description:
    "Decision support for Ayurvedic products: market, regulatory, patent and ABS analysis.",
};

// Marks the document as JS-enabled before first paint so [data-reveal]
// elements can start hidden for GSAP without a flash.
const JS_FLAG = "document.documentElement.classList.add('js')";

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html
      lang="en"
      suppressHydrationWarning
      className={`${geistSans.variable} ${geistMono.variable} ${jakarta.variable} ${devanagari.variable} h-full antialiased`}
    >
      <head>
        <script dangerouslySetInnerHTML={{ __html: JS_FLAG }} />
      </head>
      <body className="flex min-h-full flex-col bg-canvas font-sans text-ink">
        <KnowledgeGraphProvider>
          <SourceScopeProvider>
            <AgentShell>
              <SiteHeader />
              <div className="flex flex-1 flex-col">{children}</div>
              <SiteFooter />
            </AgentShell>
          </SourceScopeProvider>
        </KnowledgeGraphProvider>
      </body>
    </html>
  );
}
