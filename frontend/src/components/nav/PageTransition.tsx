"use client";

import { AnimatePresence, motion, useReducedMotion } from "motion/react";
import { usePathname } from "next/navigation";
import { type ReactNode } from "react";
import { FrozenRouter } from "./FrozenRouter";

const EASE = [0.22, 1, 0.36, 1] as const;

/**
 * Cross-fades the marketing page content on route change: the current page fades
 * out, then the new page fades in (mode="wait", so they never overlap). The
 * Header and Footer live outside this wrapper and stay put across navigations.
 *
 * Opacity-only — deliberately no transform/scale/blur. A transformed (or blurred)
 * ancestor establishes a containing block that breaks `position: sticky`/`fixed`
 * descendants such as the home page's 500vh laptop showcase; opacity does not.
 * It's also the most minimal, GPU-friendly cross-fade (no layout reflow). Exit is
 * quicker than enter so leaving feels responsive and arriving feels settled.
 * Respects prefers-reduced-motion (instant swap).
 */
export function PageTransition({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const reduce = useReducedMotion();

  return (
    <AnimatePresence mode="wait" initial={false}>
      <motion.div
        key={pathname}
        initial={reduce ? false : { opacity: 0 }}
        animate={{ opacity: 1, transition: { duration: reduce ? 0 : 0.35, ease: EASE } }}
        exit={{ opacity: reduce ? 1 : 0, transition: { duration: reduce ? 0 : 0.22, ease: EASE } }}
      >
        <FrozenRouter>{children}</FrozenRouter>
      </motion.div>
    </AnimatePresence>
  );
}
