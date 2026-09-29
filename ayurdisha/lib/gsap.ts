"use client";

import gsap from "gsap";
import { useGSAP } from "@gsap/react";
import { DrawSVGPlugin } from "gsap/DrawSVGPlugin";
import { MotionPathPlugin } from "gsap/MotionPathPlugin";
import { ScrollTrigger } from "gsap/ScrollTrigger";

// Register once for the whole app; import gsap only from this module.
if (typeof window !== "undefined") {
  gsap.registerPlugin(useGSAP, ScrollTrigger, DrawSVGPlugin, MotionPathPlugin);
}

/** Media query for users who have not asked for reduced motion. */
export const MOTION_OK = "(prefers-reduced-motion: no-preference)";

export { gsap, ScrollTrigger, useGSAP };
