# Fast + tastefully-animated marketing frontend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the Next.js marketing site feel fast and add Akris-style motion (header entrance, per-word hero text, directional section reveals, a full-screen branded page-change spinner) while keeping & lightly optimizing the 3D laptop — then consolidate the codebase onto one animation library and hand the distilled standards to the Website Builder + Design Prompt agents.

**Architecture:** Wire up primitives the codebase already ships (`Reveal`, `TextReveal`, stagger variants, the branded `LoadingScreen`) rather than build new ones; add one app-level `LazyMotion`/`MotionConfig` so motion works site-wide; trigger the branded loader on navigation via a delegated click listener + `usePathname` commit; switch the laptop Canvas to on-demand rendering; migrate the remaining `framer-motion` files to `motion/react` (drop-in) and drop the second runtime.

**Tech Stack:** Next.js 16 (App Router, Turbopack), React 19, TypeScript, `motion/react` (Motion v12), `@react-three/fiber` + `drei` + `three`, Tailwind v4, Vitest.

## Global Constraints

- Standard animation library is **`motion/react`** — never `framer-motion`. End state: `framer-motion` removed from `frontend/package.json` and zero `from "framer-motion"` imports under `frontend/src`.
- Shared motion tokens (reuse, do not reinvent): `REVEAL_EASE = [0.16, 1, 0.3, 1]` (ease-out-expo); entrance durations ~**0.4–0.6s**; **exit faster than enter**; directional travel **16–40px**; slight stagger (next beat starts before previous ends).
- All motion lives under a single `MotionConfig reducedMotion="user"` (added app-level in Task 3). Bespoke loops (laptop) lock to a sensible static state under reduced motion.
- `PageTransition` stays **opacity-only** (no transform/scale/blur) — a transformed/blurred ancestor breaks the home page's `position: sticky` 500vh laptop scene. Do **not** modify `PageTransition`.
- The page-change spinner is a `position: fixed` overlay (the existing `LoadingScreen`, `z-[9999]`) — no transformed ancestor, so the sticky scene is unaffected.
- **Surgical changes:** the library migration is an **import-source swap only** (`from "framer-motion"` → `from "motion/react"`), behavior-preserving — no refactors, no visual changes. Visual/motion work is marketing-scoped; the migration necessarily spans dashboard files (they import `framer-motion`).
- **Do NOT use `strict` on `LazyMotion`** — full `motion` components are used across the app and `strict` rejects them.
- **Commits:** Per Stefan's standing preference, do **not** `git commit` unless he explicitly says so. The "Commit" steps below are **checkpoints** — run the verification, then hold the actual commit until Stefan approves. Stage nothing destructive.
- Verification gate for any task that builds: `npm run typecheck`, `npm run build`, `npm run test` (run from `frontend/`) all green.

---

### Task 1: Route-loader decision helper (pure, unit-tested)

The only unit-testable piece of the spinner: decide whether a clicked anchor is a real client-side navigation that should show the loader.

**Files:**
- Create: `frontend/src/lib/route-loader.ts`
- Test: `frontend/src/lib/__tests__/route-loader.test.ts`

**Interfaces:**
- Produces: `shouldTriggerRouteLoad({ href, currentOrigin, currentPath }: { href: string | null | undefined; currentOrigin: string; currentPath: string }): boolean`

- [ ] **Step 1: Write the failing test**

```ts
// frontend/src/lib/__tests__/route-loader.test.ts
import { describe, it, expect } from "vitest";
import { shouldTriggerRouteLoad } from "../route-loader";

const ORIGIN = "https://roman-technologies.dev";
const at = (href: string | null, currentPath = "/") =>
  shouldTriggerRouteLoad({ href, currentOrigin: ORIGIN, currentPath });

describe("shouldTriggerRouteLoad", () => {
  it("triggers for an internal route to a different path", () => {
    expect(at("/about")).toBe(true);
  });
  it("does not trigger for a same-page hash link", () => {
    expect(at("/#contact", "/")).toBe(false);
    expect(at("#contact", "/")).toBe(false);
  });
  it("triggers for a different path even with a hash", () => {
    expect(at("/about#team", "/")).toBe(true);
  });
  it("does not trigger for external links", () => {
    expect(at("https://example.com/x")).toBe(false);
  });
  it("ignores mailto/tel and empty href", () => {
    expect(at("mailto:a@b.com")).toBe(false);
    expect(at("tel:+311234")).toBe(false);
    expect(at(null)).toBe(false);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd frontend && npx vitest run src/lib/__tests__/route-loader.test.ts`
Expected: FAIL — `shouldTriggerRouteLoad is not a function` / module not found.

- [ ] **Step 3: Write minimal implementation**

```ts
// frontend/src/lib/route-loader.ts
/**
 * Decides whether an anchor click should trigger the full-screen route loader.
 * Pure + framework-free so it is unit-testable. Returns true only for a real
 * client-side navigation to a DIFFERENT pathname on the same origin.
 */
export function shouldTriggerRouteLoad({
  href,
  currentOrigin,
  currentPath,
}: {
  href: string | null | undefined;
  currentOrigin: string;
  currentPath: string;
}): boolean {
  if (!href) return false;
  if (/^(mailto:|tel:|#)/i.test(href)) return false;
  let url: URL;
  try {
    url = new URL(href, currentOrigin);
  } catch {
    return false;
  }
  if (url.origin !== currentOrigin) return false; // external
  if (!/^https?:$/.test(url.protocol)) return false;
  if (url.pathname === currentPath) return false; // same page (pure hash)
  return true;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd frontend && npx vitest run src/lib/__tests__/route-loader.test.ts`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit (checkpoint — hold per no-auto-commit)**

```bash
git add frontend/src/lib/route-loader.ts frontend/src/lib/__tests__/route-loader.test.ts
# commit only when Stefan approves:
# git commit -m "feat(marketing): route-load decision helper"
```

---

### Task 2: Branded page-change spinner (RouteLoader + LoadingScreen → motion/react + wiring)

**Files:**
- Create: `frontend/src/components/nav/RouteLoader.tsx`
- Modify: `frontend/src/components/ui/LoadingScreen.tsx:3` (import source)
- Modify: `frontend/src/app/(marketing)/providers.tsx` (mount `<RouteLoader/>`)

**Interfaces:**
- Consumes: `shouldTriggerRouteLoad` (Task 1); `useLoading()` → `{ show(): void; hide(): void }` from `@/context/loading`.
- Produces: `export function RouteLoader(): null`

- [ ] **Step 1: Migrate the loader to the standard library**

In `frontend/src/components/ui/LoadingScreen.tsx`, change line 3 only:

```ts
// from:
import { motion, AnimatePresence } from "framer-motion";
// to:
import { motion, AnimatePresence } from "motion/react";
```

(Identical API. Once the app-level `MotionConfig reducedMotion="user"` exists in Task 3, the ring/shimmer transform animations auto-pause under reduced motion, leaving a static branded screen — no extra code.)

- [ ] **Step 2: Create the RouteLoader**

```tsx
// frontend/src/components/nav/RouteLoader.tsx
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
```

- [ ] **Step 3: Mount it in MarketingProviders**

In `frontend/src/app/(marketing)/providers.tsx`, add the import and render `<RouteLoader/>` next to `<ScrollToTopOnNavigate/>` (both inside `LoadingProvider`). Full file after Task 3 is shown there; for now add:

```tsx
import { RouteLoader } from "@/components/nav/RouteLoader";
// ...inside <AuthProvider>, after <ScrollToTopOnNavigate />:
<RouteLoader />
```

- [ ] **Step 4: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.
Manual (dev server, `npm run dev`): click About/Clients/Team/Contact and the Log In button → the branded conic-ring + shimmer loader appears immediately and fades out after the new page renders (~0.45s min). Clicking an in-page anchor on the same page (e.g. "See pricing" / nav hash on home) shows **no** loader. The home 500vh laptop scene still scrolls/sticks normally.

- [ ] **Step 5: Commit (checkpoint — hold per no-auto-commit)**

```bash
git add frontend/src/components/nav/RouteLoader.tsx frontend/src/components/ui/LoadingScreen.tsx "frontend/src/app/(marketing)/providers.tsx"
# git commit -m "feat(marketing): branded full-screen spinner on route change"
```

---

### Task 3: App-level LazyMotion + MotionConfig provider

So any `Reveal`/`TextReveal` using the light `m` component animates everywhere (today they silently no-op outside `HeroSection`), and reduced-motion is centralized.

**Files:**
- Modify: `frontend/src/app/(marketing)/providers.tsx`

**Interfaces:**
- Consumes: `RouteLoader` (Task 2).
- Produces: a `LazyMotion features={domAnimation}` + `MotionConfig reducedMotion="user"` ancestor wrapping the entire marketing tree (Header, main, Footer).

- [ ] **Step 1: Replace the providers file**

```tsx
// frontend/src/app/(marketing)/providers.tsx
"use client";

import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import { LoadingProvider } from "@/context/loading";
import { AuthProvider } from "@/context/auth";
import { ScrollToTopOnNavigate } from "@/components/nav/ScrollToTopOnNavigate";
import { RouteLoader } from "@/components/nav/RouteLoader";

export function MarketingProviders({ children }: { children: React.ReactNode }) {
  return (
    // NOTE: no `strict` — full `motion` components (LoadingScreen, PageTransition,
    // HeaderRightCluster) are used across the app and strict mode rejects them.
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <LoadingProvider>
          <AuthProvider>
            <ScrollToTopOnNavigate />
            <RouteLoader />
            {children}
          </AuthProvider>
        </LoadingProvider>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 2: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS (no "motion component within a LazyMotion with strict mode" error — confirms `strict` is absent).
Manual: home hero still animates (HeroSection keeps its own inner provider — nesting is fine). With OS "reduce motion" on, entrances become instant fades and the spinner ring stops spinning.

- [ ] **Step 3: Commit (checkpoint — hold)**

```bash
git add "frontend/src/app/(marketing)/providers.tsx"
# git commit -m "feat(marketing): app-level LazyMotion + reduced-motion config"
```

---

### Task 4: Hero headline per-word reveal

**Files:**
- Modify: `frontend/src/components/hero/HeroSection.tsx`

**Interfaces:**
- Consumes: `TextReveal` from `@/components/motion/TextReveal`; app-level `LazyMotion` (Task 3) or HeroSection's own inner provider (either suffices).

- [ ] **Step 1: Import TextReveal**

Add to the imports block of `HeroSection.tsx`:

```ts
import { TextReveal } from "@/components/motion/TextReveal";
```

- [ ] **Step 2: Replace the single-block `m.h1` (lines 73–80) with a per-word cascade**

```tsx
<TextReveal
  as="h1"
  by="word"
  direction="up"
  text={HEADLINE_TEXT}
  delay={D_HEADLINE}
  stagger={0.05}
  duration={FADE}
  distance="0.5em"
  className="max-w-[20ch] font-display text-[clamp(2.5rem,7vw,6rem)] font-bold leading-[0.96] tracking-[-0.02em] text-text-primary"
/>
```

Notes: `TextReveal`'s default `ease` is `REVEAL_EASE` which equals the hero's `EXPO` (`[0.16,1,0.3,1]`), so `ease` is omitted (avoids a readonly-tuple type mismatch). `direction="up"` makes each word drop in from above, matching the old `y:-28`. `D_HEADLINE`, `FADE`, and `HEADLINE_TEXT` are unchanged so the beat slots into the existing choreography. `m` is still used by the surrounding `m.p` elements — no orphaned import.

- [ ] **Step 3: Taste pass**

Invoke the `ui-ux-pro-max` and `frontend-design` skills (per Stefan's request) to sanity-check the cascade rhythm vs. the subtext beat; tune `stagger` (0.04–0.07) and `distance` (`0.4em`–`0.6em`) only if it reads sluggish or jumpy. Keep it subtle.

- [ ] **Step 4: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.
Manual: on the home hero, the headline reveals word-by-word (dropping from above), flowing into the subtext; screen-reader announces the full headline once (TextReveal sets `aria-label`).

- [ ] **Step 5: Commit (checkpoint — hold)**

```bash
git add frontend/src/components/hero/HeroSection.tsx
# git commit -m "feat(marketing): per-word hero headline reveal"
```

---

### Task 5: Header staggered entrance

**Files:**
- Modify: `frontend/src/components/Header.tsx`

**Interfaces:**
- Consumes: `m` from `motion/react`; `stagger`, `fadeDown` variant objects from `@/lib/animations`; app-level `LazyMotion` (Task 3, required — Header sits in the marketing layout, outside HeroSection's provider).

- [ ] **Step 1: Update imports**

```ts
import { m, useScroll, useMotionValueEvent } from "motion/react";
import { stagger, fadeDown } from "@/lib/animations";
```

(`useScroll`/`useMotionValueEvent` already imported from `motion/react`; just add `m`.)

- [ ] **Step 2: Replace the `return (...)` block (lines 41–65)**

```tsx
  return (
    <header
      ref={ref}
      className="fixed left-0 right-0 top-0 z-40 border-b border-transparent"
    >
      <m.div
        variants={stagger}
        initial="hidden"
        animate="visible"
        className="mx-auto flex h-14 max-w-7xl items-center justify-between px-4 sm:h-16 sm:px-6 lg:px-8"
      >
        <m.div variants={fadeDown}>
          <Logo />
        </m.div>

        <div className="flex items-center gap-1 md:gap-2">
          <nav className="hidden items-center gap-1 md:flex" aria-label="Primary navigation">
            {NAV_LINKS.map((link) => (
              <m.div key={link.label} variants={fadeDown}>
                <NavLink href={link.href} className={`px-4 py-2 ${navLinkCn}`}>
                  {link.label}
                </NavLink>
              </m.div>
            ))}
          </nav>

          <HeaderRightCluster />
        </div>
      </m.div>
    </header>
  );
```

Notes: the `animate-fade-down` CSS class is removed from `<header>` (the JS stagger replaces the bar fade — static bar, children wave in, Akris-style). The `ref` + scroll-blur logic on `<header>` is untouched. `HeaderRightCluster` is **not** wrapped (it returns a flex group of auth slot + hamburger that must stay direct flex children; wrapping would break its layout) — only Logo + nav links are stagger children. The `stagger` variant (`staggerChildren 0.09, delayChildren 0.3`) sequences Logo → links via motion-tree propagation (intermediate plain `nav`/`div` are transparent to variant propagation).

- [ ] **Step 3: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.
Manual: on first load, the logo then the nav links fade/drop in left-to-right; spacing/alignment identical to before; scrolling still fades the bar background/blur in smoothly; mobile hamburger + drawer unaffected.

- [ ] **Step 4: Commit (checkpoint — hold)**

```bash
git add frontend/src/components/Header.tsx
# git commit -m "feat(marketing): staggered header nav entrance"
```

---

### Task 6: Directional section reveals on static marketing sections

Apply the existing `Reveal` (scroll-triggered, directional, consistent easing) to major marketing sections that currently have no entrance, for the Akris "pop-in from direction" feel. Taste-driven and repetitive — same recipe per section.

**Files (discover, then modify):**
- Modify: marketing section components/pages that render static blocks — candidates: `frontend/src/app/(marketing)/contact/page.tsx`, `frontend/src/app/(marketing)/team/page.tsx`, `frontend/src/app/(marketing)/about/page.tsx`, `frontend/src/app/(marketing)/clients/page.tsx`, and home-page section components under `frontend/src/components/` (e.g. pricing/contact/what-we-do sections rendered by `frontend/src/app/(marketing)/page.tsx`).

**Interfaces:**
- Consumes: `Reveal` from `@/components/motion/Reveal` (props: `inView`, `direction`, `distance`, `delay`, `duration`, `amount`, `repeat`); app-level `LazyMotion` (Task 3).

- [ ] **Step 1: Discover targets & avoid double-animating**

Run: `cd frontend && grep -rln "Reveal\|whileInView\|<motion\|<m\." "src/app/(marketing)" src/components | sort`
Use this to (a) find sections that ALREADY animate (skip them) and (b) confirm which section blocks are static. Open `src/app/(marketing)/page.tsx` to map which components compose the home page.

- [ ] **Step 2: Apply the reveal recipe to each static section**

Recipe (wrap the section's heading/content block; for grids, stagger cards by index):

```tsx
import { Reveal } from "@/components/motion/Reveal";

// Single block — rises in on scroll:
<Reveal inView direction="up" distance={28} duration={0.6}>
  <h2 className="...">Section heading</h2>
</Reveal>

// Card grid — alternate/lateral pop-in, staggered by index:
{items.map((item, i) => (
  <Reveal key={item.id} inView direction={i % 2 ? "right" : "left"} distance={32} delay={i * 0.08}>
    <Card {...item} />
  </Reveal>
))}
```

Constraints: keep `distance` in 16–40px, `duration` 0.4–0.6s, default `amount` (0.3), `once` (do not pass `repeat`) so each section animates a single time. Do not wrap elements that are `position: sticky`/`fixed` (would re-introduce a transformed ancestor) — wrap their inner content instead. Match the project's existing `Reveal` call style found in Step 1.

- [ ] **Step 3: Taste pass (where to apply / how much)**

Invoke `frontend-design` + `ui-ux-pro-max` (per Stefan's request) to decide which sections benefit and to keep motion restrained (hero + nav already animate; avoid animating every element — pick section headers and primary content blocks). Less is more.

- [ ] **Step 4: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.
Manual: scroll About/Team/Contact/Clients and the home sections — headings/cards rise/slide in once as they enter view; nothing flickers; reduced-motion shows fades without travel; sticky laptop scene intact.

- [ ] **Step 5: Commit (checkpoint — hold)**

```bash
git add -A "frontend/src/app/(marketing)" frontend/src/components
# git commit -m "feat(marketing): scroll-triggered section reveals"
```

---

### Task 7: Laptop Canvas → on-demand rendering

Stop re-rendering identical frames when the laptop sits at a static state while still near the viewport.

**Files:**
- Modify: `frontend/src/components/hero/LaptopScene.tsx`
- Modify (optional safeguard): `frontend/src/components/hero/LaptopShowcase.tsx`

**Interfaces:**
- Consumes: `useThree` from `@react-three/fiber`; the `progress` `MotionValue` + `active` boolean already passed into `LaptopScene`.

- [ ] **Step 1: Add `useThree` to the fiber import**

```ts
// frontend/src/components/hero/LaptopScene.tsx — line 4
import { Canvas, useFrame, useThree } from "@react-three/fiber";
```

- [ ] **Step 2: Add a scroll invalidator component (after `CameraRig`, before `LaptopScene`)**

```tsx
// Drives on-demand rendering: with frameloop="demand" the Canvas only paints
// when invalidate() is called. We invalidate on every scroll-progress change
// while the section is active, so scrubbing stays smooth but a static laptop
// (user stopped scrolling) stops repainting identical frames. The !warming
// effect paints one settling frame when the warm-up loop ends.
function ScrollInvalidator({
  progress,
  active,
  warming,
}: {
  progress: MotionValue<number>;
  active: boolean;
  warming: boolean;
}) {
  const invalidate = useThree((s) => s.invalidate);
  const activeRef = useRef(active);
  activeRef.current = active;

  useEffect(() => {
    if (!warming) invalidate();
  }, [warming, invalidate]);

  useEffect(() => {
    const unsub = progress.on("change", () => {
      if (activeRef.current) invalidate();
    });
    return unsub;
  }, [progress, invalidate]);

  return null;
}
```

Add `useRef` to the React import on line 3:

```ts
import { useEffect, useRef, useState } from "react";
```

- [ ] **Step 3: Switch the Canvas frameloop and mount the invalidator**

In `LaptopScene`'s `<Canvas>` (line 65), change:

```tsx
// from:
frameloop={warming || active ? "always" : "never"}
// to:
frameloop={warming ? "always" : "demand"}
```

And add the invalidator as the first child inside `<Canvas>` (just before `<CameraRig .../>`):

```tsx
<ScrollInvalidator progress={progress} active={active} warming={warming} />
```

Notes: `warming` (220ms after mount) still renders every frame to compile shaders/upload geometry. After that it's `demand`: scroll → `progress` change → `invalidate()` → paint; idle near-viewport → no paint (the win); scrolled away (`active` false) → no paint. Reduced motion (CameraRig fixes `p=0.5`) still gets a correct static pose from the warm frames + the `!warming` settle paint.

- [ ] **Step 4 (optional safeguard): gate the idle warm in LaptopShowcase**

Low value for this layout (the showcase sits ~1 viewport below the hero, so it is essentially always near), but harmless. In `LaptopShowcase.tsx`, inside the idle `requestIdleCallback`/`setTimeout` warm (lines ~143–149), only warm when the section is within ~2 viewports:

```tsx
const t = window.setTimeout(() => {
  const top = sectionRef.current?.getBoundingClientRect().top ?? 0;
  if (top > window.innerHeight * 2) return; // far below — let nearView mount it instead
  if (typeof window.requestIdleCallback === "function") {
    idleId = window.requestIdleCallback(() => setIdleWarmed(true), { timeout: 1000 });
  } else {
    setIdleWarmed(true);
  }
}, 800);
```

If this adds noticeable complexity vs. benefit during review, **skip it** — the frameloop change is the substantive win.

- [ ] **Step 5: Verify build + manual**

Run: `cd frontend && npm run typecheck && npm run build`
Expected: PASS.
Manual (desktop): scroll through the home laptop section — the lid-open/camera scrub is smooth; stop scrolling mid-section and confirm GPU/CPU usage drops (DevTools Performance / no constant repaint) instead of holding high; reduced-motion shows a correct static laptop; mobile still shows the CSS fallback (no WebGL).

- [ ] **Step 6: Commit (checkpoint — hold)**

```bash
git add frontend/src/components/hero/LaptopScene.tsx frontend/src/components/hero/LaptopShowcase.tsx
# git commit -m "perf(marketing): on-demand laptop Canvas rendering"
```

---

### Task 8: Consolidate onto motion/react (remove framer-motion)

Mechanical, behavior-preserving import-source swap across the remaining `framer-motion` files, then drop the dependency.

**Files:**
- Modify: every file under `frontend/src` importing `framer-motion` (≈34 after Task 2 migrated `LoadingScreen`) — includes `frontend/src/components/Footer.tsx`, `frontend/src/components/HeaderRightCluster.tsx`, and the `components/admin/*`, `components/leads/*`, `components/dashboard/*` sets.
- Modify: `frontend/src/lib/animations.ts:1` (the `import type { Variants }`).
- Modify: `frontend/package.json` (remove `framer-motion`).

- [ ] **Step 1: Enumerate the remaining importers**

Run: `cd frontend && grep -rln 'from "framer-motion"\|from '"'"'framer-motion'"'"'' src`
Expected: the list of files still importing `framer-motion` (≈34). Note the count.

- [ ] **Step 2: Swap the import source in every file (import lines only)**

Run (Git Bash):

```bash
cd frontend
grep -rln 'from "framer-motion"\|from '"'"'framer-motion'"'"'' src \
  | while read -r f; do
      sed -i -E "s#from ['\"]framer-motion['\"]#from \"motion/react\"#g" "$f"
    done
```

This rewrites only `from "framer-motion"` / `from 'framer-motion'` import sources (comments mentioning "framer-motion", e.g. in `context/loading.tsx`, are left untouched). `motion`, `AnimatePresence`, `useReducedMotion`, `Variants`, `m`, `LazyMotion`, `domAnimation` and all hooks exist identically in `motion/react` (Motion v12 is the renamed framer-motion) — drop-in.

- [ ] **Step 3: Remove the dependency**

Edit `frontend/package.json`: delete the `"framer-motion": "^12.34.3",` line from `dependencies`. Then:

Run: `cd frontend && npm install`
(updates `package-lock.json` to drop `framer-motion`).

- [ ] **Step 4: Verify zero imports + full gate**

Run:
```bash
cd frontend
grep -rn 'from "framer-motion"\|from '"'"'framer-motion'"'"'' src   # expect: no output
npm run typecheck
npm run build
npm run test
```
Expected: grep prints nothing; typecheck/build/test all PASS. (If any file used a `framer-motion`-only deep import like `framer-motion/dom`, surface it — none were found in the scan; resolve case-by-case to the `motion/react` equivalent.)

- [ ] **Step 5: Commit (checkpoint — hold)**

```bash
git add -A frontend
# git commit -m "refactor: consolidate framer-motion -> motion/react, drop framer-motion"
```

---

### Task 9: Formal handoff — Motion & Performance Standards to the two agents

Write the distilled, durable standards into the agent instruction files so future builds follow them.

**Files:**
- Modify: `agents/Website Builder/learnings-template/conventions.md` (append the standards section)
- Modify: `agents/Website Builder/phases/8-verify.md` (append a motion/perf checklist)
- Modify: `agents/Website Builder/phases/4-implement.md` (add a one-line pointer)
- Modify: `agents/Design Prompt creator/phases/5-generate.md` (require motion + spinner + perf budgets in generated briefs)
- Modify: `agents/Design Prompt creator/AGENTS.md` (add a principles pointer)

- [ ] **Step 1: Read each target file first**

Open each of the 5 files to match its existing heading style/voice before inserting (do not restructure existing content — append a clearly-titled section).

- [ ] **Step 2: Append this "Motion & Performance Standards" section to `conventions.md`**

```markdown
## Motion & Performance Standards

1. **One animation library per project — `motion/react`.** Never mix `framer-motion` and `motion/react` on a page (breaks shared `layoutId`/`AnimatePresence` and ships two runtimes). Consolidating onto `motion/react` is part of "done".
2. **One shared motion token set.** Define easing + base durations + standard distances once and reuse via primitives (`Reveal`, `TextReveal`, slide-in factory, stagger container) — no ad-hoc inline motion objects. Consistent feel = "intentional"; per-component invented timing = "AI slop".
3. **Tree-shake the runtime, enforce the contract.** Use `LazyMotion` + `domAnimation` + the `m` component, but provide ONE app-level `LazyMotion` provider so `m` components can't silently no-op (an `m` component outside a `LazyMotion` ancestor renders dead markup). Do not use `strict` if full `motion` components are also used.
4. **Honor `prefers-reduced-motion` globally** via a single `MotionConfig reducedMotion="user"` near the root, plus an explicit static fallback in any bespoke scroll/RAF/3D code.
5. **Scroll-triggered entrances are the workhorse:** fade + small directional travel (16–40px), ease-out/spring, fire once on viewport entry; durations ~0.3–0.6s; stagger children slightly (next beat starts before previous finishes). Large travel / long durations read as sluggish.
6. **Page transitions: opacity-only cross-fade**, `AnimatePresence mode="wait"`, exit faster than enter. NEVER transform/scale/blur the transition wrapper if the page has `position: sticky`/`fixed` scroll scenes — a transformed ancestor breaks them.
7. **Ship a branded page-load / navigation spinner as a first-class deliverable.** Lightweight CSS/single-MotionValue spinner that loads instantly; trigger via a route-aware boundary or a tiny route-change listener; min-display window so it never flashes.
8. **Keep the `'use client'` boundary thin:** server-render most HTML, push client to provider/island level, lazy-load heavy/below-the-fold modules (3D, charts, video) with `ssr:false` + a skeleton that prevents layout shift; pre-warm the chunk on idle and mount on viewport-intersection.
9. **Viewport-aware render loops:** run continuous animation (RAF / WebGL frameloop / scroll-scrub) only near the viewport; freeze when away. Prefer on-demand rendering (`frameloop="demand"` + `invalidate()` on input change) over always-on. Channel scroll-linked work through a SINGLE RAF loop.
10. **3D/WebGL heroes:** cap `dpr` (~1.5), bake the environment procedurally (no HDR fetch → no network failure mode), warm shaders ~200ms after mount, and ALWAYS provide a static CSS/image fallback on mobile so WebGL never loads on small/low-power devices.
11. **Stale-while-revalidate data layer** with in-flight de-duplication and content-tiered freshness (static ≈ infinite, semi-static minutes/hours, volatile short TTL); serve cached instantly, revalidate in the background.
12. **Server-first data fetching for first paint; avoid client fetch waterfalls.** Kick off independent requests together; reserve `force-dynamic` for genuinely per-request auth-gated pages; use pure-CSS streaming skeletons for route-segment loading.
```

- [ ] **Step 3: Append the verify checklist to `phases/8-verify.md`**

```markdown
### Motion & performance checklist
- [ ] Single animation library (`motion/react`); no `framer-motion` imports remain.
- [ ] One app-level `LazyMotion` + `MotionConfig reducedMotion="user"`; no `m` component renders outside it.
- [ ] Page-load / navigation spinner present and triggers on route change (min-display, no flash).
- [ ] Entrance motion is restrained (16–40px travel, 0.3–0.6s, fires once); page transition is opacity-only.
- [ ] Heavy/3D modules are `ssr:false` + skeleton + mobile fallback; render loops are viewport-aware / on-demand.
- [ ] `npm run typecheck` + `npm run build` + tests green; reduced-motion verified.
```

- [ ] **Step 4: Add the pointer to `phases/4-implement.md`**

Append: `> Motion & performance: follow the "Motion & Performance Standards" in learnings-template/conventions.md (one library = motion/react, shared tokens, app-level LazyMotion + reduced-motion, restrained scroll reveals, branded nav spinner, on-demand 3D, server-first data).`

- [ ] **Step 5: Update Design Prompt creator `phases/5-generate.md`**

Append a requirement that generated design briefs MUST specify: (a) tasteful, restrained motion — header entrance, per-word hero text reveal, scroll-triggered directional section reveals with shared easing/timing; (b) a branded page-load/navigation spinner as a named element; (c) performance budgets — fast LCP, lazy-load heavy media/3D, `prefers-reduced-motion` support. Phrase it in the file's existing voice. Sell "fast + tastefully animated", never gratuitous motion.

- [ ] **Step 6: Add the pointer to Design Prompt creator `AGENTS.md`**

Append a short note: design prompts must encode the Motion & Performance Standards (restrained motion with shared tokens, a first-class loading spinner, performance budgets, reduced-motion) so downstream builds are fast and tastefully animated by default.

- [ ] **Step 7: Commit (checkpoint — hold)**

```bash
git add "agents/Website Builder" "agents/Design Prompt creator"
# git commit -m "docs(agents): motion & performance standards for builder + design-prompt agents"
```

---

## Self-Review

**Spec coverage:**
- WS1 page spinner → Tasks 1+2 ✓
- WS2 hero text reveal → Task 4 ✓
- WS3 header stagger → Task 5 ✓
- WS4 app-level LazyMotion + section reveals → Tasks 3 + 6 ✓
- WS5 laptop perf → Task 7 (frameloop demand core; idle-warm gate optional) ✓
- WS6 consolidation → Task 8 (LoadingScreen done early in Task 2) ✓
- Deliverable (agent handoff) → Task 9 ✓
- Deferred items (CountUp, cache TTL tiers, poster, visited-path) → intentionally absent ✓

**Placeholder scan:** No "TBD/handle edge cases" — Task 6 gives a concrete recipe + discovery command (the per-section application is repetitive, not vague). Agent-doc content is provided verbatim.

**Type/name consistency:** `shouldTriggerRouteLoad` signature identical in Task 1 (def), test, and Task 2 (use); `RouteLoader` consistent Tasks 2→3; `ScrollInvalidator` props match its usage in Task 7; variant names `stagger`/`fadeDown` match `lib/animations.ts`.

**Order/dependencies:** 1→2 (helper before component); 3 before 5 (Header needs app-level LazyMotion); 3 before 6 (section Reveals need it); 2's `LoadingScreen` migration removes it from Task 8's set; 8 last so the zero-import gate is final.
