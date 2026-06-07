"use client";

import { useEffect, useState } from "react";

/**
 * SSR-safe viewport query. Returns `true` on the first (server + initial
 * client) render so the R3F branch is assumed and layout height is stable,
 * then hydrates to the real match on mount to avoid a CLS jump. Default
 * breakpoint is the 768px mobile cutoff from the hero spec.
 */
export function useIsDesktop(minWidth = 768): boolean {
  const [isDesktop, setIsDesktop] = useState(true);

  useEffect(() => {
    const mq = window.matchMedia(`(min-width: ${minWidth}px)`);
    const update = () => setIsDesktop(mq.matches);
    update();
    mq.addEventListener("change", update);
    return () => mq.removeEventListener("change", update);
  }, [minWidth]);

  return isDesktop;
}
