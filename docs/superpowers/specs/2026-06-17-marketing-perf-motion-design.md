# Fast + tastefully-animated marketing frontend (Akris-inspired)

**Date:** 2026-06-17
**Status:** Approved (design) — pending implementation plan
**Scope:** `frontend/` marketing surface for all *visual* work; codebase-wide for the
`framer-motion → motion/react` consolidation (required to drop the second runtime).
Plus a formal handoff of distilled principles to the **Website Builder** and
**Design Prompt creator** agents. No backend, i18n, booking, or auth changes.

## Overview

The user perceives the Next.js marketing frontend as "a bit slow" and wants
Akris-style motion (header entrance, per-word hero text, directional pop-in
reveals) plus a page-change loading spinner, while keeping the 3D laptop hero.

A read-only scan (11 agents) of both the Akris React app
(`C:\Users\stefa\OneDrive\Desktop\Akris`, Vite + GSAP/framer-motion) and the CMS
frontend established the key reframe: **the CMS frontend is already
well-architected.** It already has thin `'use client'` boundaries, the full
`motion/react` primitive system (`Reveal`, `TextReveal`, `createSlideIn`,
stagger), `LazyMotion` + reduced-motion config, a *superior* `PageTransition`
(opacity-only + `FrozenRouter`), a sophisticated SWR cache, and a heavily
optimized 3D laptop (lazy mount, viewport-gated frameloop, dpr cap, mobile
fallback). The laptop is **not** the bottleneck.

The real, fixable causes of the "slow / less-polished" feel are:

1. **No page-navigation spinner** — route changes show nothing; the branded
   `LoadingScreen` only fires on auth login/logout.
2. **Two animation libraries shipped** — 35 files still import `framer-motion`
   (extra runtime weight + mixed-library page risk).
3. **Hero headline animates as one block** — the per-word `TextReveal` exists but
   isn't wired into the H1.
4. **Header nav has no staggered entrance** — only a CSS `animate-fade-down`.
5. **`Reveal` silently no-ops outside the hero** — the light `m` component needs a
   `LazyMotion` ancestor; only `HeroSection` provides one, so sections elsewhere
   look static.
6. **Laptop `frameloop='always'`** near the viewport re-renders identical frames at
   static end-states.

Almost every requested item is achievable with **small, low-risk changes because
the primitives already exist**. The single large item is the library
consolidation.

## Decisions (resolved during brainstorming)

1. **Scope:** Visual/motion work is **marketing-only**. The page spinner + perf
   wins apply where relevant. The library consolidation spans the codebase
   (including dashboard files) because removing `framer-motion` from the bundle
   *requires* migrating its consumers — this is a mechanical, behavior-preserving
   import-path swap, not a refactor.
2. **Spinner style:** **Full-screen branded (Akris-style)** — reuse the existing
   conic-ring + shimmer `LoadingScreen` on every marketing navigation, with a
   min-display window to prevent flicker.
3. **Library consolidation:** **Full now** — migrate all ~35 `framer-motion`
   consumers to `motion/react` and remove `framer-motion` from `package.json`.
4. **Laptop 3D:** **Keep and optimize** (it is already well-contained); apply only
   `frameloop='demand'` + idle-warm gating.
5. **Optional adds deferred (out of scope):** `CountUp` animated-stat primitive and
   codified cache-TTL tiers. Documented as future follow-ups; not built here
   (keeps the change surgical and marketing-scoped).

## Architecture / approach

Reuse-first: wire up existing primitives rather than build new ones. Motion stays
consistent with the existing tokens — `REVEAL_EASE` (`[0.16, 1, 0.3, 1]`,
expo-out), entrance durations ~0.4–0.6s, **exit faster than enter** for
transitions, small directional travel (16–40px), slight stagger (start the next
beat before the previous finishes). All motion remains under a single
`MotionConfig reducedMotion="user"`.

The full-screen spinner is a `position: fixed` overlay, so it introduces **no
transformed ancestor** — it is safe alongside the 500vh sticky laptop scene
(which is exactly why `PageTransition` is opacity-only). The `PageTransition`
component is **kept as-is**.

During implementation, the `ui-ux-pro-max`, `frontend-design`, and
`motion-animations` skills inform choreography, timing, and where-to-apply
decisions (per the user's explicit request).

## Workstreams (file-by-file)

### WS1 — Page-change spinner (full-screen branded) · S · low risk

- **New** `frontend/src/components/nav/RouteLoader.tsx` (client): bridges
  navigation events to the existing loader.
  - `show()` on navigation **start**; `hide()` when navigation **commits**.
  - Trigger model (Next 16 App Router has no router-events API):
    - **Start:** Next 16 `Link onNavigate` on the centralized marketing nav links,
      plus a delegated `document` click listener as a fallback for internal
      `a[href]` links not routed through the shared component (same-origin,
      unmodified click only).
    - **Commit:** a `usePathname()` (and `useSearchParams()` if needed) effect
      calls `hide()`.
  - **Min-display ~400ms** so instant client navs still show the branded loader
    cleanly without flicker; reduced-motion → static branded screen (no spin).
- **Modified** `frontend/src/app/(marketing)/providers.tsx` — mount `<RouteLoader/>`
  next to `ScrollToTopOnNavigate`, inside the existing loading context provider.
- Reuse `frontend/src/context/loading.tsx` (`useLoading` show/hide) and
  `frontend/src/components/ui/LoadingScreen.tsx` (migrated to `motion/react` in
  WS6) — no new loader visuals.

### WS2 — Hero headline per-word reveal · S · low risk

- **Modified** `frontend/src/components/hero/HeroSection.tsx` — replace the
  single-block `m.h1` with `<TextReveal as="h1" by="word">`
  (`frontend/src/components/motion/TextReveal.tsx`), preserving the existing EXPO
  ease and the `D_HEADLINE` delay so it slots into the current multi-beat
  choreography. `HeroSection` already provides a `LazyMotion` ancestor.

### WS3 — Header nav staggered entrance · S · low risk

- **Modified** `frontend/src/components/Header.tsx` — wrap the logo + the
  `NAV_LINKS.map()` output in a `motion/react` stagger container (children:
  `y:-12 → 0`, opacity 0→1; ~0.08s stagger; **first-load only**). Keep the
  existing scroll-driven `backdrop-blur`/background logic (`useScroll` +
  `useMotionValueEvent`) untouched. Relies on the WS4 app-level `LazyMotion`
  ancestor (Header sits in the marketing layout).

### WS4 — App-level LazyMotion provider + section reveals · S→M · low/med risk

- **Modified** `frontend/src/app/(marketing)/providers.tsx` — add one
  `LazyMotion features={domAnimation}` + `MotionConfig reducedMotion="user"`
  wrapping the marketing tree, so any `Reveal`/`TextReveal` using the light `m`
  component animates everywhere (today they silently no-op outside `HeroSection`).
  - Verify no double-provider conflict with `HeroSection`'s own `LazyMotion`
    (nesting the same `domAnimation` features is safe; remove the inner one only if
    redundant and safe to do so).
- **Modified** marketing section components currently static — apply the existing
  `Reveal` (directional, 16–40px, `REVEAL_EASE`, `viewport once:true`,
  stagger-by-index): Contact, Pricing, Team, About-story sections (exact files
  enumerated in the implementation plan; `WhatWeDo`/`ProjectsGrid` already animate
  and are extended only if inconsistent).

### WS5 — Laptop 3D perf · M · med risk

- **Modified** `frontend/src/components/hero/LaptopScene.tsx` — change `frameloop`
  from the binary `'always'/'never'` viewport toggle to **`'demand'`** + call
  `invalidate()` on the scroll `progress` MotionValue change (and during the ~220ms
  warm) so identical frames are not re-rendered at static end-states. Keep dpr cap,
  baked procedural environment, and the single shared Lenis+motion RAF loop.
- **Modified** `frontend/src/components/hero/LaptopShowcase.tsx` — gate the
  `requestIdleCallback` warm-mount so it only runs when the hero is within ~1.5
  viewports (skip the full Three.js mount on bounce sessions). Preserve the
  dual-trigger (`nearView` OR `idleWarmed`) and Lenis snap behavior.
- Static high-quality poster image = **optional stretch**, not required.

### WS6 — Full motion/react consolidation · L · med risk

- **Modified** `frontend/src/lib/animations.ts` — change
  `import type { Variants } from "framer-motion"` to `"motion/react"`.
- **Modified** all remaining `framer-motion` consumers (35 files total today,
  enumerated via `grep -rl "framer-motion" frontend/src` at implementation time):
  includes `frontend/src/components/Footer.tsx`,
  `frontend/src/components/ui/LoadingScreen.tsx`, and the
  `components/admin/*`, `components/leads/*`, `components/dashboard/*` sets.
  - **Drop-in import-path swap only** (`framer-motion` → `motion/react`). The
    `AnimatePresence` / `motion` / `m` / `Variants` / hooks APIs are
    source-compatible. **No behavioral or visual refactors** (per the global
    surgical-changes rule); every changed line is an import source.
- **Modified** `frontend/package.json` — remove the `framer-motion` dependency.
- **Verification gate:** `grep -rl "framer-motion" frontend/src` returns **zero**;
  `npm run typecheck`, `npm run build`, and `npm run test` (vitest) all green.

## Deliverable — formal handoff to the two agents

Distill the 12 scan principles into a durable **"Motion & Performance Standards"**
section, written into the agent instruction files so future builds follow them:

- **Website Builder** (`agents/Website Builder/`):
  - `learnings-template/conventions.md` — the durable standards (one library =
    `motion/react`; shared motion tokens; `LazyMotion` + `m` contract; global
    `reducedMotion='user'`; scroll-trigger reveal recipe; opacity-only page
    transition w/ sticky-scene caveat; first-class branded nav spinner; thin
    `'use client'` + lazy heavy modules; viewport-aware render loops + single RAF;
    3D/WebGL hero rules; SWR + content-tiered caching; server-first fetch / no
    waterfalls).
  - `phases/8-verify.md` — add a motion/perf checklist item (no mixed libraries;
    spinner present; reduced-motion respected; reveals fire; build/typecheck green).
  - `phases/4-implement.md` — a brief pointer to the conventions section.
- **Design Prompt creator** (`agents/Design Prompt creator/`):
  - `phases/5-generate.md` — generated briefs must specify tasteful motion
    (header/hero/section reveals with restrained timing), a page-load/navigation
    spinner as a first-class element, and performance budgets (LCP, lazy heavy
    media, reduced-motion).
  - `AGENTS.md` — a short principles note pointing at the standard.

The 12 principles (verbatim source for the handoff sections) are recorded in the
scan synthesis and will be transcribed into the above files during implementation.

## Testing strategy

- **Unit/component:** existing `vitest` suite must stay green; add focused tests
  only where a new component (`RouteLoader`) has testable logic (show/hide +
  min-display + reduced-motion branch), mocking `usePathname`.
- **Build/type:** `npm run typecheck` + `npm run build` green (Turbopack).
- **Bundle:** confirm `framer-motion` absent from the build (zero imports +
  removed from `package.json`).
- **Manual (dev server):** spinner fires on every marketing nav and hides cleanly;
  no FOUC; hero per-word reveal + header stagger play once; section reveals fire on
  scroll; the 500vh sticky laptop scene is intact; reduced-motion disables
  spin/entrance travel.

## Out of scope / future

- `CountUp` animated-stat primitive (`components/motion/CountUp.tsx`).
- Codified cache-TTL tiers for the dashboard `useQuery` call sites.
- Static laptop poster image.
- Visited-path tracking to skip re-animation on intra-session revisits.
- Any dashboard *visual* changes (consolidation aside).

## Risks & mitigations

- **Consolidation regressions** — mitigated by import-only swaps, full
  typecheck/build/test gate, and zero-import grep verification.
- **Double `LazyMotion`** (WS4 vs `HeroSection`) — verify nesting is safe; only
  remove the inner provider if proven redundant.
- **Spinner flicker / stuck loader** — min-display window + commit-on-`pathname`
  effect with a safety timeout to force-hide.
- **Spinner vs sticky laptop** — overlay is `position: fixed` (no transform), so
  the sticky scene is unaffected; `PageTransition` stays opacity-only.
