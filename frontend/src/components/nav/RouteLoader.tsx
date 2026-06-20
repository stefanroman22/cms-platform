"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";
import { useLoading } from "@/context/loading";
import { shouldTriggerRouteLoad } from "@/lib/route-loader";

/** Minimum time (ms) the branded loader stays up so instant client navs
 *  don't make it flash. */
const MIN_DISPLAY = 450;
/** Safety net: force-hide if a navigation never commits (cancelled click etc.). */
const SAFETY_TIMEOUT = 6000;

/**
 * Shows the branded full-screen LoadingScreen on marketing route navigations.
 * App Router has no router-events API, so:
 *   • START — a capture-phase delegated click listener detects internal,
 *     same-origin links to a different path and calls show().
 *   • COMMIT — a usePathname() effect calls hide() once the new route renders,
 *     respecting MIN_DISPLAY so the loader is always seen cleanly.
 * Must be mounted inside <LoadingProvider>.
 */
export function RouteLoader() {
  const pathname = usePathname();
  const { show, hide } = useLoading();
  const shownAtRef = useRef<number | null>(null);
  const firstRender = useRef(true);
  const safetyRef = useRef<number | undefined>(undefined);

  // START: catch internal nav clicks anywhere in the document.
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented) return;
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const anchor = (e.target as Element | null)?.closest?.("a");
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return; // new tab/window
      if (anchor.hasAttribute("download")) return;
      if (
        !shouldTriggerRouteLoad({
          href: anchor.getAttribute("href"),
          currentOrigin: window.location.origin,
          currentPath: window.location.pathname,
        })
      )
        return;
      shownAtRef.current = performance.now();
      show();
      window.clearTimeout(safetyRef.current);
      safetyRef.current = window.setTimeout(() => hide(), SAFETY_TIMEOUT);
    };
    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, [show, hide]);

  // COMMIT: hide on pathname change (after MIN_DISPLAY).
  useEffect(() => {
    if (firstRender.current) {
      firstRender.current = false;
      return;
    }
    window.clearTimeout(safetyRef.current);
    const shownAt = shownAtRef.current;
    const elapsed = shownAt == null ? MIN_DISPLAY : performance.now() - shownAt;
    const remaining = Math.max(0, MIN_DISPLAY - elapsed);
    const id = window.setTimeout(() => {
      hide();
      shownAtRef.current = null;
    }, remaining);
    return () => window.clearTimeout(id);
  }, [pathname, hide]);

  return null;
}
