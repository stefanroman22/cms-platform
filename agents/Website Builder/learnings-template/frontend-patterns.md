# Frontend Architecture & Motion Patterns (reference implementation)

Concrete, copy-usable patterns that REALIZE the high-level rules in `conventions.md`
("Motion & Performance Standards"). Read the rules there for the *why and the budgets*;
read this for the *how* — real component shapes, token values, and hook signatures lifted
from the CMS frontend's Akris-inspired motion/perf pass. Translate to the build's design
tokens; do NOT copy palette/wordmark verbatim. Maps 1:1 to the Phase 8 "Motion and
performance checklist" — each pattern below satisfies one or more of its line items.

---

## 1. Canonical provider stack (ONE app-level LazyMotion, no `strict`)

Mount exactly one provider island in the root layout route. Order matters: motion runtime →
global reduced-motion → loading overlay state → auth → nav side-effects. In the Vite SPA
the root layout is a component in `src/routes.tsx` that wraps `<Outlet />`; `Header`/`Footer`
render as static markup around `<PageTransition><Outlet /></PageTransition>` inside it. No
`'use client'` directive — every component is already client-side.

```tsx
// src/routes.tsx — RootLayout (wraps <Outlet />; providers live here, NOT around a router)
import { Outlet } from "react-router-dom";
import { I18nextProvider } from "react-i18next";
import { QueryClientProvider } from "@tanstack/react-query";
import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
import i18n from "@/i18n/config";
import { queryClient } from "@/lib/query";
// NOTE: no `strict` — full `motion` components (loading overlay, page transition,
// mobile drawer) are used and strict mode rejects anything but `m.*`.

function RootLayout() {
  return (
    <I18nextProvider i18n={i18n}>
      <QueryClientProvider client={queryClient}>
        <LazyMotion features={domAnimation}>
          <MotionConfig reducedMotion="user">
            <LoadingProvider>
              <AuthProvider>
                <ScrollToTopOnNavigate />
                <RouteLoader />
                <Outlet />
              </AuthProvider>
            </LoadingProvider>
          </MotionConfig>
        </LazyMotion>
      </QueryClientProvider>
    </I18nextProvider>
  );
}
```

If the build is single-context (no auth) drop `AuthProvider`; keep the rest. The whole stack
is the home of the "one app-level LazyMotion + `MotionConfig`" checklist item.

---

## 2. Page-change loading spinner (React Router + Suspense fallback)

Two-phase pattern — **START** on a delegated capture-phase click, **COMMIT** on the
`useLocation()` change — plus a min-display window and a safety net. The decision of *whether*
a click is a real internal nav is a PURE, unit-testable helper (no React, no framework).

`src/components/RouteLoader.tsx` is used as the `<Suspense fallback={<RouteLoader />}>` on
every lazy route in `src/routes.tsx`. It also doubles as the delegated-click spinner for
instant client navigations via React Router, covering the case where the chunk is already
cached but the URL has changed.

```ts
// src/lib/route-loader.ts — pure + testable
export function shouldTriggerRouteLoad({ href, currentOrigin, currentPath }: {
  href: string | null | undefined; currentOrigin: string; currentPath: string;
}): boolean {
  if (!href) return false;
  if (/^(mailto:|tel:|#)/i.test(href)) return false;       // mailto/tel/hash-only
  let url: URL;
  try { url = new URL(href, currentOrigin); } catch { return false; }
  if (url.origin !== currentOrigin) return false;          // external
  if (!/^https?:$/.test(url.protocol)) return false;
  if (url.pathname === currentPath) return false;          // same page
  return true;
}
```

```tsx
// src/components/RouteLoader.tsx — mounted inside <LoadingProvider>
// Used both as a Suspense fallback and as a delegated-click spinner.
import { useEffect, useRef } from "react";
import { useLocation } from "react-router-dom";
import { shouldTriggerRouteLoad } from "@/lib/route-loader";

const MIN_DISPLAY = 450;     // never flash on instant client navs
const SAFETY_TIMEOUT = 6000; // force-hide if a nav never commits (cancelled click)

export function RouteLoader() {
  const { pathname } = useLocation();
  const firstRender = useRef(true);
  const shownAtRef = useRef<number | null>(null);
  const safetyRef = useRef<ReturnType<typeof setTimeout>>(undefined);
  const { show, hide } = useLoadingContext(); // from <LoadingProvider>

  // START — capture phase fires before React handlers
  useEffect(() => {
    const onClick = (e: MouseEvent) => {
      if (e.defaultPrevented) return;
      if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return;
      const anchor = (e.target as Element | null)?.closest?.("a");
      if (!anchor) return;
      if (anchor.target && anchor.target !== "_self") return;
      if (anchor.hasAttribute("download")) return;
      if (!shouldTriggerRouteLoad({ href: anchor.getAttribute("href"),
            currentOrigin: location.origin, currentPath: location.pathname })) return;
      shownAtRef.current = performance.now();
      show();
      clearTimeout(safetyRef.current);
      safetyRef.current = setTimeout(() => hide(), SAFETY_TIMEOUT);
    };
    document.addEventListener("click", onClick, { capture: true });
    return () => document.removeEventListener("click", onClick, { capture: true });
  }, [show, hide]);

  // COMMIT — pathname effect hides after MIN_DISPLAY (firstRender guard skips initial load)
  useEffect(() => {
    if (firstRender.current) { firstRender.current = false; return; }
    clearTimeout(safetyRef.current);
    const elapsed = shownAtRef.current == null ? MIN_DISPLAY : performance.now() - shownAtRef.current;
    const remaining = Math.max(0, MIN_DISPLAY - elapsed);
    const id = setTimeout(() => { hide(); shownAtRef.current = null; }, remaining);
    return () => clearTimeout(id);
  }, [pathname, hide]);

  return null; // visual overlay rendered by LoadingProvider
}
```

The overlay itself is `position: fixed z-[9999]` so it sits above sticky headers/menus — keep
it at the top of the provider tree and ensure NO ancestor has a transform (a transformed
ancestor creates a stacking context and breaks `fixed`). Lazy the overlay so its motion code
never ships on cold load:

```tsx
// src/context/loading.tsx
import { lazy } from "react";

const LoadingScreen = lazy(() =>
  import("@/components/ui/LoadingScreen").then((m) => ({ default: m.LoadingScreen }))
);
// render {isVisible && <Suspense fallback={null}><LoadingScreen isVisible={isVisible} /></Suspense>}
// from the provider — spinner + arc CSS load only when shown
```

In `src/routes.tsx`, every lazy page is wrapped in `<Suspense fallback={<RouteLoader />}>`:

```tsx
import { lazy, Suspense } from "react";
import { RouteLoader } from "@/components/RouteLoader";

const HomePage = lazy(() => import("@/pages/HomePage"));

{ index: true, element: <Suspense fallback={<RouteLoader />}><HomePage /></Suspense> }
```

---

## 3. Shared motion tokens + header staggered entrance

Define tokens ONCE and reuse via variants. Real values from the CMS frontend:

```ts
// src/lib/animations.ts
import type { Variants } from "motion/react";

export const REVEAL_EASE = [0.16, 1, 0.3, 1] as const; // ease-out-expo — the signature curve
export const fadeDown: Variants = { hidden: { opacity: 0, y: -16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } } };
export const fadeUp: Variants = { hidden: { opacity: 0, y: 16 },
  visible: { opacity: 1, y: 0, transition: { duration: 0.45, ease: "easeOut" } } };
export const stagger: Variants = { hidden: {},
  visible: { transition: { staggerChildren: 0.09, delayChildren: 0.3 } } };
export const staggerFast: Variants = { hidden: {},   // compact lists / mobile drawer
  visible: { transition: { staggerChildren: 0.06, delayChildren: 0.12 } } };
```

Header = a `stagger` container with `fadeDown` children (logo + each nav link). **Do NOT wrap
the right-side cluster** (auth buttons / locale switcher / hamburger) in a motion child — it
must stay a direct flex child so it never animates/delays on auth-state toggles:

```tsx
import { m } from "motion/react";
import { stagger, fadeDown } from "@/lib/animations";

<m.div variants={stagger} initial="hidden" animate="visible" className="flex h-14 …">
  <m.div variants={fadeDown}><Logo /></m.div>
  <nav className="hidden md:flex">
    {NAV_LINKS.map((l) => <m.div key={l.label} variants={fadeDown}><NavLink {...l} /></m.div>)}
  </nav>
  <HeaderRightCluster /> {/* NOT wrapped — direct child */}
</m.div>
```

Scroll-driven header lift: bind background/border/blur directly to scroll via
`useMotionValueEvent(scrollY, "change", …)` over a `FADE_RANGE` (~100px) so the surface lifts
continuously (`rgba(…, 0.9*t)` + `blur(12*t px)`), never a hard threshold toggle.

---

## 4. Hero — per-word `TextReveal` + multi-beat overlapping choreography

The hero is the ONE place to spend boldness. Tokenize the headline per word, stagger each
token; orchestrate eyebrow / headline / subtext / actions as overlapping beats (delay gap <
fade duration so beats stack, not lockstep). Container carries `aria-label` (full string),
tokens are `aria-hidden`.

```tsx
// hero choreography (src/components/sections/HeroSection.tsx)
import { m } from "motion/react";
import { TextReveal } from "@/components/ui/TextReveal";

const FADE = 0.5, STAGGER = 0.28, EXPO = [0.16, 1, 0.3, 1] as const; // STAGGER < FADE => overlap
const D_EYEBROW = 0.1, D_HEADLINE = 0.38, D_SUBTEXT = 0.66, D_ACTIONS = 0.94;

<m.p initial={{ opacity: 0, y: -18 }} animate={{ opacity: 1, y: 0 }}
     transition={{ duration: FADE, ease: EXPO, delay: D_EYEBROW }} />        {/* eyebrow drops in */}
<TextReveal as="h1" by="word" text={HEADLINE} delay={D_HEADLINE} stagger={0.05} duration={FADE} />
<m.p initial={{ opacity: 0, y: 20 }} animate={{ opacity: 1, y: 0 }}
     transition={{ duration: FADE, ease: EXPO, delay: D_SUBTEXT }} />        {/* subtext rises */}
// buttons + trust badges + support line all share delay={D_ACTIONS} (one FadeIn wrapper, DRY)
```

```tsx
// src/components/ui/TextReveal.tsx — one m.span per token, per-token delay = delay + i*stagger
import { createElement } from "react";
import { m } from "motion/react";
import { REVEAL_EASE } from "@/lib/animations";

export function TextReveal({
  as: Tag = "p", by = "word", text, delay = 0, stagger = 0.05, duration = 0.5,
}: TextRevealProps) {
  const tokens = text.split(" ");                 // by="word"
  const hidden = { opacity: 0, y: "-0.5em" };    // directionOffset("up")
  return createElement(Tag, { "aria-label": text }, tokens.map((t, i) => (
    <m.span key={i} aria-hidden="true" className="inline-block whitespace-pre-wrap"
      initial={hidden} animate={{ opacity: 1, x: 0, y: 0 }}
      transition={{ duration, ease: REVEAL_EASE, delay: delay + i * stagger }}>{t}</m.span>
  )));
}
```

Optional scroll cue (ChevronDown) loops only AFTER the hero settles: `delay = D_ACTIONS + FADE + 0.2`.

---

## 5. GRID STAGGER = ONE container trigger, never per-card index*delay (the stale-delay bug)

The single most common motion bug. For any grid/list of cards (team, services, projects),
put `whileInView` + `viewport` on the PARENT container with `staggerFast`; children declare
only `variants={fadeUp}` and NO `whileInView` of their own.

```tsx
import { m } from "motion/react";
import { staggerFast, fadeUp } from "@/lib/animations";

// parent — the ONLY whileInView
<m.div variants={staggerFast} initial="hidden" whileInView="visible"
       viewport={{ once: true, amount: 0.15 }}
       className="grid grid-cols-1 gap-6 sm:grid-cols-2 lg:grid-cols-3">
  {members.map((mb) => <TeamMemberCard key={mb.name} member={mb} />)}
</m.div>
// child — no whileInView; container's staggerChildren drives the cascade
<m.article variants={fadeUp} className="flex flex-col">…</m.article>
```

**Why never per-card `whileInView` + `index*delay`:** later cards that are ALREADY on screen
sit invisible until their fixed delay elapses, then pop after the user has scrolled past — a
jarring, blocking reveal. Tying the stagger to the container's viewport entry fixes it.

---

## 6. Active-underline alignment under a `first:pl-0` tab (carousel/tab strip gotcha)

An absolutely-positioned active-tab underline using a symmetric inset (e.g. `inset-x-2.5` =
`left:10px`) misaligns under the FIRST tab when that tab is flush-left via `first:pl-0`. Match
the underline's left offset to the button's actual padding:

```tsx
<button className="relative shrink-0 px-2.5 py-1.5 … first:pl-0">
  {label}
  {isActive && (
    <span className={cn("absolute bottom-0 right-2.5 h-0.5 rounded-full bg-accent",
      i === 0 ? "left-0" : "left-2.5")} /> // first tab flush-left => left-0
  )}
</button>
```

---

## 7. Heavy / 3D modules — dual-trigger mount + `frameloop="demand"` + invalidate + mobile fallback

Never let a Three.js/WebGL hero block first paint. Pattern:

```tsx
// src/components/sections/LaptopShowcase.tsx — pre-warm + dual trigger
import { lazy, Suspense, useEffect, useState } from "react";
import { useInView } from "motion/react";

useEffect(() => { void import("./LaptopScene"); }, []);                 // kick the network fetch now
const nearView = useInView(sectionRef, { margin: "0px 0px -120px 0px", once: true });
// + a requestIdleCallback(…, { timeout: 1000 }) ~800ms after mount sets idleWarmed
const showScene = nearView || idleWarmed;                               // whichever fires first
if (!isDesktop) return <MobileLaptopFallback />;                        // CSS/DOM mock, no WebGL on phones
const LaptopScene = lazy(() => import("./LaptopScene"));
// render: {showScene && <Suspense fallback={<HeroSceneSkeleton />}><LaptopScene /></Suspense>}
```

```tsx
// src/components/sections/LaptopScene.tsx — on-demand render
// only repaints on scroll/warm-up, not 60fps at rest
<Canvas dpr={[1, 1.5]} frameloop={warming ? "always" : "demand"}     // warm ~220ms then demand
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}>
  <Environment resolution={256} frames={1}> {/* procedural Lightformers — NO HDR fetch, no network failure */}
    <Lightformer intensity={2.4} … color="#ffffff" /> …
  </Environment>
</Canvas>
// ScrollInvalidator: progress.on("change", () => active && invalidate()) ties repaint to scroll ticks
```

Drive smooth-scroll (Lenis) and motion off a SINGLE RAF loop
(`useAnimationFrame((t) => lenis.raf(t))`) so scroll progress, Lenis, and R3F advance on one
tick — never competing loops. Skip the whole loop on `prefers-reduced-motion`.

---

## 8. TanStack Query data layer (`useQuery`) — localStorage-persisted + inflight dedup

Serve cached data instantly, revalidate in the background, never refetch the same key twice in
parallel. The `QueryClient` is localStorage-persisted via `persistQueryClient` +
`createSyncStoragePersister` (set up in `src/lib/query.ts` from `vite-react-scaffolding`), so
hard reloads paint sub-1s from the persisted cache.

```ts
// src/lib/query.ts (shape from vite-react-scaffolding)
import { QueryClient } from "@tanstack/react-query";
import { persistQueryClient } from "@tanstack/react-query-persist-client";
import { createSyncStoragePersister } from "@tanstack/query-sync-storage-persister";

export const queryClient = new QueryClient({
  defaultOptions: { queries: { staleTime: 2 * 60_000 } }, // 2-min default TTL
});

persistQueryClient({
  queryClient,
  persister: createSyncStoragePersister({ storage: window.localStorage }),
});
```

Consuming CMS content in a page component:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

export function ServicesSection() {
  const { t } = useTranslation();
  const { data } = useQuery({
    queryKey: ["cms", "services"],
    queryFn: () => fetch(`${import.meta.env.VITE_CMS_ENDPOINT}/services`).then((r) => r.json()),
    staleTime: 5 * 60_000,
  });
  // falls back to bundled t("services.items") from messages/<locale>.json until CMS returns data
  const items = data ?? (t("services.items", { returnObjects: true }) as ServiceItem[]);
  return <>{items.map((item) => <ServiceCard key={item.id} {...item} />)}</>;
}
```

Tier `staleTime` by volatility: static content ≈ `Infinity`, semi-static `minutes/hours`, volatile short.
Fire independent requests together (no waterfall). Global app state (locale choice, booking
state, UI flags) lives in Zustand `persist` stores in `src/lib/store.ts`.
