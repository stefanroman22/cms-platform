"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { getActiveLenis } from "@/lib/scroll";

/**
 * Resets scroll to the top of the page on every route change — clicking a nav
 * or footer link to another page should land you at the top, not wherever you
 * were scrolled before (e.g. leaving the home footer for /about). Lenis (home
 * only) holds the old scroll offset, so Next's default reset doesn't take; this
 * forces it for both the window and Lenis. Skipped on first mount and when the
 * URL has a hash, so initial loads and in-page anchors keep their own position.
 */
export function ScrollToTopOnNavigate() {
  const pathname = usePathname();
  const firstRender = useRef(true);

  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    if (window.location.hash) return;
    // Re-assert a couple of times: the browser / Next can restore the previous
    // scroll a frame or two after the new page mounts.
    const toTop = () => {
      window.scrollTo(0, 0);
      getActiveLenis()?.scrollTo(0, { immediate: true });
    };
    toTop();
    const raf = requestAnimationFrame(toTop);
    const timer = setTimeout(toTop, 100);
    return () => {
      cancelAnimationFrame(raf);
      clearTimeout(timer);
    };
  }, [pathname]);

  return null;
}
