"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, useState } from "react";
import { Dishu } from "@/components/mascot/Dishu";
import { NAV } from "@/lib/nav";

/** Hand-drawn stroke under the active link, echoing the hero underline. */
function Squiggle() {
  return (
    <svg
      aria-hidden
      viewBox="0 0 100 8"
      preserveAspectRatio="none"
      className="absolute -bottom-2 left-0 h-2 w-full"
    >
      <path
        d="M2 5 C 20 1, 40 7, 60 4 S 90 2, 98 5"
        fill="none"
        stroke="var(--turmeric)"
        strokeWidth="3"
        strokeLinecap="round"
        vectorEffect="non-scaling-stroke"
      />
    </svg>
  );
}

export function SiteHeader() {
  const pathname = usePathname();
  const [scrolled, setScrolled] = useState(false);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    const onScroll = () => setScrolled(window.scrollY > 8);
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  return (
    <header
      className={`sticky top-0 z-40 bg-canvas transition-colors duration-200 ${
        scrolled || open ? "border-b border-line" : "border-b border-transparent"
      }`}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center gap-10 px-4 sm:px-6">
        <Link
          href="/"
          className="flex items-center gap-2.5"
          onClick={() => setOpen(false)}
        >
          <Dishu size={34} animated={false} title="" />
          <span className="flex flex-col leading-none">
            <span className="font-display text-lg font-extrabold tracking-tight">
              AyurDisha
            </span>
            <span className="font-devanagari text-[11px] text-muted">
              आयुर्दिशा
            </span>
          </span>
        </Link>

        <nav className="hidden items-center gap-7 whitespace-nowrap text-[15px] lg:flex">
          {NAV.map((n) => {
            const active = pathname.startsWith(n.href);
            return (
              <Link
                key={n.href}
                href={n.href}
                aria-current={active ? "page" : undefined}
                className={`relative py-1 transition-colors ${
                  active ? "font-semibold text-ink" : "text-muted hover:text-ink"
                }`}
              >
                {n.label}
                {active && <Squiggle />}
              </Link>
            );
          })}
        </nav>

        <div className="ml-auto flex items-center gap-3">
          <Link
            href="/review"
            className="group hidden items-center gap-2 rounded-lg bg-ink px-4 py-2 whitespace-nowrap text-sm font-semibold text-canvas transition-colors hover:bg-leaf sm:inline-flex"
          >
            Start analysis
            <span className="transition-transform group-hover:translate-x-0.5">
              →
            </span>
          </Link>
          <button
            type="button"
            className="grid h-10 w-10 place-items-center rounded-lg text-ink hover:bg-mint lg:hidden"
            aria-label={open ? "Close menu" : "Open menu"}
            aria-expanded={open}
            onClick={() => setOpen((o) => !o)}
          >
            <svg width="20" height="20" viewBox="0 0 20 20" aria-hidden>
              <path
                d={open ? "M4 4 L16 16 M16 4 L4 16" : "M3 6 H17 M3 10 H17 M3 14 H11"}
                stroke="currentColor"
                strokeWidth="1.8"
                strokeLinecap="round"
              />
            </svg>
          </button>
        </div>
      </div>

      {open && (
        <nav className="border-t border-line px-4 pb-6 lg:hidden">
          <ul className="mx-auto max-w-6xl divide-y divide-line">
            {NAV.map((n) => {
              const active = pathname.startsWith(n.href);
              return (
                <li key={n.href}>
                  <Link
                    href={n.href}
                    onClick={() => setOpen(false)}
                    className={`flex items-center justify-between py-4 font-display text-lg ${
                      active ? "font-bold text-ink" : "text-muted"
                    }`}
                  >
                    {n.label}
                    <span className={active ? "text-turmeric" : "text-line"}>→</span>
                  </Link>
                </li>
              );
            })}
          </ul>
          <Link
            href="/review"
            onClick={() => setOpen(false)}
            className="mt-4 block rounded-lg bg-ink px-4 py-3 text-center font-semibold text-canvas sm:hidden"
          >
            Start analysis →
          </Link>
        </nav>
      )}
    </header>
  );
}
