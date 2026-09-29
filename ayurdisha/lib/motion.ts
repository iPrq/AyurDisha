"use client";

import { gsap } from "@/lib/gsap";

/**
 * Adds a "draw the outline, then fill" pass for spot icons (shapes with the
 * `si` class) to a timeline at `position`.
 */
export function drawIcons(
  tl: gsap.core.Timeline,
  icons: Element | Element[] | null | undefined,
  position?: gsap.Position,
  duration = 0.8,
) {
  const list = (Array.isArray(icons) ? icons : icons ? [icons] : []).flatMap((i) =>
    Array.from(i.querySelectorAll(".si")),
  );
  if (!list.length) return tl;
  return tl
    .fromTo(
      list,
      { drawSVG: "0%" },
      { drawSVG: "100%", duration, ease: "power1.inOut" },
      position,
    )
    .from(list, { fillOpacity: 0, duration: 0.4, ease: "none" }, `-=${duration * 0.45}`);
}
