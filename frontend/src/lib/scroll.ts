import type Lenis from "lenis";

/**
 * Smooth in-page scrolling that works from anywhere — including the Header,
 * which lives OUTSIDE the marketing page's <LenisProvider> and so cannot read
 * the Lenis React context. The provider registers its instance here; any
 * component can then `scrollToHash` and get the same Lenis-driven motion (with
 * a graceful native fallback when Lenis is absent / reduced-motion).
 */

let activeLenis: Lenis | null = null;

export function setActiveLenis(instance: Lenis | null) {
  activeLenis = instance;
}

/** The active Lenis instance, if the current page mounted one (home only). */
export function getActiveLenis(): Lenis | null {
  return activeLenis;
}

/** Space left above the target so the fixed header doesn't cover it. */
export const HEADER_OFFSET = 90;

// ── Programmatic-scroll flag ────────────────────────────────────────────────
// A scrollToHash() jump flies the scroll across the page in ~1s. Scroll-linked
// scenes (the laptop showcase) would scrub through their whole timeline during
// that jump and look glitchy. We flip this flag for the duration of the jump so
// those scenes can freeze instead — manual scrolling never sets it, so normal
// scroll behaviour is unchanged.
let programmatic = false;
const progListeners = new Set<(v: boolean) => void>();
let progTimer: ReturnType<typeof setTimeout> | null = null;

function setProgrammatic(v: boolean) {
  if (progTimer) {
    clearTimeout(progTimer);
    progTimer = null;
  }
  if (programmatic === v) return;
  programmatic = v;
  progListeners.forEach((l) => l(v));
}

/** Start the programmatic window, auto-clearing after `maxMs` as a safety net
 *  in case the scroll is interrupted before it completes. */
function beginProgrammatic(maxMs: number) {
  setProgrammatic(true);
  progTimer = setTimeout(() => setProgrammatic(false), maxMs);
}

export function isProgrammaticScroll() {
  return programmatic;
}

export function subscribeProgrammaticScroll(fn: (v: boolean) => void) {
  progListeners.add(fn);
  return () => {
    progListeners.delete(fn);
  };
}

/** Resolve an "#id" / "/#id" / "id" string to the element id. */
function targetId(hash: string): string {
  return hash.replace(/^.*#/, "");
}

/** Smooth-scroll to the section with the given hash/id. No-op if not found. */
export function scrollToHash(hash: string) {
  if (typeof window === "undefined") return;
  const id = targetId(hash);
  if (!id) return;
  const el = document.getElementById(id);
  if (!el) return;

  if (activeLenis) {
    beginProgrammatic(1500);
    activeLenis.scrollTo(el, {
      offset: -HEADER_OFFSET,
      duration: 1.1,
      onComplete: () => setProgrammatic(false),
    });
    return;
  }

  const top = el.getBoundingClientRect().top + window.scrollY - HEADER_OFFSET;
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  beginProgrammatic(reduce ? 50 : 900);
  window.scrollTo({ top, behavior: reduce ? "auto" : "smooth" });
}
