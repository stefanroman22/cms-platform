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

/** Gap left between the fixed header and the heading of a jumped-to section, so
 *  the heading sits just below the bar rather than flush against it. */
const HEADING_GAP = 10;

/** Live height of the fixed site header (h-14 → 56px mobile / h-16 → 64px
 *  desktop). Selected by `position: fixed` so the decorative <header> inside the
 *  hero CMS mock is ignored. Falls back to the desktop height before first paint. */
function fixedHeaderHeight(): number {
  if (typeof document === "undefined") return 64;
  for (const h of Array.from(document.querySelectorAll("header"))) {
    if (getComputedStyle(h).position === "fixed") {
      return Math.round(h.getBoundingClientRect().height);
    }
  }
  return 64;
}

/** Viewport-relative top of a section's visible content (its heading block),
 *  skipping absolutely-positioned decoration (the ambient glows). Anchoring to
 *  the content — not the section's padded box edge — means a section's large top
 *  padding OR vertical centering (e.g. the min-h-dvh pricing section) doesn't
 *  leave the heading stranded far down the viewport. */
function contentTop(section: HTMLElement): number {
  for (const child of Array.from(section.children)) {
    if (child instanceof HTMLElement && getComputedStyle(child).position !== "absolute") {
      return child.getBoundingClientRect().top;
    }
  }
  return section.getBoundingClientRect().top;
}

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

// ── Settle re-pin ───────────────────────────────────────────────────────────
// The home page keeps reflowing for a beat after a jump — the async 3D hero
// scene mounts, the booking calendar fetches its month — which can leave a
// one-shot target a couple dozen px off (heading tucked behind the header).
// While `programmatic` is set the laptop showcase pauses its scroll-snap, so we
// can safely re-pin the heading until the layout stops moving, bailing the
// instant the user scrolls so we never fight them.
let stopSettle: (() => void) | null = null;

/** Smooth-scroll to the section with the given hash/id. No-op if not found. */
export function scrollToHash(hash: string) {
  if (typeof window === "undefined") return;
  const id = targetId(hash);
  if (!id) return;
  const el = document.getElementById(id);
  if (!el) return;
  stopSettle?.();

  // Scroll position that puts the section's heading — not its padded or
  // vertically-centered box edge — ~HEADING_GAP px below the fixed header.
  const desiredTop = () =>
    Math.max(0, contentTop(el) + window.scrollY - fixedHeaderHeight() - HEADING_GAP);

  if (activeLenis) {
    const lenis = activeLenis;
    beginProgrammatic(4000);
    lenis.scrollTo(desiredTop(), {
      duration: 1.1,
      onComplete: () => {
        // Re-pin through late layout settling; stop on user scroll or timeout.
        let ticks = 0;
        const stop = () => {
          clearInterval(timer);
          window.removeEventListener("wheel", stop);
          window.removeEventListener("touchstart", stop);
          window.removeEventListener("keydown", stop);
          stopSettle = null;
          setProgrammatic(false);
        };
        const tick = () => {
          const d = desiredTop();
          if (Math.abs(window.scrollY - d) > 2) lenis.scrollTo(d, { duration: 0.3 });
          if (++ticks >= 12) stop(); // ~2.4s window, enough for async content
        };
        const timer = setInterval(tick, 200);
        stopSettle = stop;
        window.addEventListener("wheel", stop, { passive: true });
        window.addEventListener("touchstart", stop, { passive: true });
        window.addEventListener("keydown", stop);
      },
    });
    return;
  }

  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  beginProgrammatic(reduce ? 50 : 900);
  window.scrollTo({ top: desiredTop(), behavior: reduce ? "auto" : "smooth" });
}
