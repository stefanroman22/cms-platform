# Frontend Architecture & Motion Patterns (reference implementation)

Concrete, copy-usable patterns that REALIZE the high-level rules in `conventions.md`
(“Motion & Performance Standards”). Read the rules there for the *why and the budgets*;
read this for the *how* — real component shapes, token values, and hook signatures lifted
from the CMS frontend's Akris-inspired motion/perf pass. Translate to the build's design
tokens; do NOT copy palette/wordmark verbatim. Maps 1:1 to the Phase 8 “Motion and
performance checklist” — each pattern below satisfies one or more of its line items.

---

## 1. Canonical provider stack (ONE app-level LazyMotion, no `strict`)

Mount exactly one provider island near the root. Order matters: motion runtime → global
reduced-motion → loading overlay state → auth → nav side-effects. The marketing `layout.tsx`
stays a Server Component and wraps this `'use client'` island; `Header`/`Footer` render as
static SSR around `<PageTransition>{children}</PageTransition>` inside it.

```tsx
// app/[locale]/providers.tsx  ('use client')
import { LazyMotion, domAnimation, MotionConfig } from "motion/react";
// NOTE: no `strict` — full `motion` components (loading overlay, page transition,
// mobile drawer) are used and strict mode rejects anything but `m.*`.
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
```

If the build is single-context (no auth) drop `AuthProvider`; keep the rest. The whole stack
is the home of the “one app-level LazyMotion + `MotionConfig`” checklist item.

---

## 2. Page-change loading spinner (App Router has no router-events API)

Two-phase pattern — **START** on a delegated capture-phase click, **COMMIT** on the
`usePathname()` change — plus a min-display window and a safety net. The decision of *whether*
a click is a real internal nav is a PURE, unit-testable helper (no React, no framework).

```ts
// lib/route-loader.ts — pure + testable
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
// components/nav/RouteLoader.tsx  ('use client') — mounted inside <LoadingProvider>
const MIN_DISPLAY = 450;     // never flash on instant client navs
const SAFETY_TIMEOUT = 6000; // force-hide if a nav never commits (cancelled click)

// START — capture phase fires before React handlers
const onClick = (e: MouseEvent) => {
  if (e.defaultPrevented) return;
  if (e.button !== 0 || e.metaKey || e.ctrlKey || e.shiftKey || e.altKey) return; // new-tab modifiers
  const anchor = (e.target as Element | null)?.closest?.("a");
  if (!anchor) return;
  if (anchor.target && anchor.target !== "_self") return;   // new tab/window
  if (anchor.hasAttribute("download")) return;
  if (!shouldTriggerRouteLoad({ href: anchor.getAttribute("href"),
        currentOrigin: location.origin, currentPath: location.pathname })) return;
  shownAtRef.current = performance.now();
  show();
  window.clearTimeout(safetyRef.current);
  safetyRef.current = window.setTimeout(() => hide(), SAFETY_TIMEOUT);
};
document.addEventListener("click", onClick, { capture: true });

// COMMIT — pathname effect hides after MIN_DISPLAY (firstRender guard skips initial load)
useEffect(() => {
  if (firstRender.current) { firstRender.current = false; return; }
  window.clearTimeout(safetyRef.current);
  const elapsed = shownAtRef.current == null ? MIN_DISPLAY : performance.now() - shownAtRef.current;
  const remaining = Math.max(0, MIN_DISPLAY - elapsed);
  const id = window.setTimeout(() => { hide(); shownAtRef.current = null; }, remaining);
  return () => window.clearTimeout(id);
}, [pathname, hide]);
```

The overlay itself is `position: fixed z-[9999]` so it sits above sticky headers/menus — keep
it at the top of the provider tree and ensure NO ancestor has a transform (a transformed
ancestor creates a stacking context and breaks `fixed`). Lazy the overlay so its motion code
never ships on cold load:

```tsx
// context/loading.tsx
const LoadingScreen = dynamic(
  () => import("@/components/ui/LoadingScreen").then((m) => ({ default: m.LoadingScreen })),
  { ssr: false } // spinner + arc CSS load only when shown; avoids SSR hydration mismatch
);
// render {isVisible && <LoadingScreen isVisible={isVisible} />} from the provider
```

This is distinct from `app/[locale]/loading.tsx` (the route-SEGMENT loader for server-render
waits, covered in conventions.md “Motion — inter-page route loader”). Both exist: the segment
loader covers RSC fetch waits, this delegated-click loader covers instant client navs.

---

## 3. Shared motion tokens + header staggered entrance

Define tokens ONCE and reuse via variants. Real values from the CMS frontend:

```ts
// lib/animations.ts
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
// hero choreography (HeroSection)
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
// TextReveal — one m.span per token, per-token delay = delay + i*stagger
const tokens = text.split(" ");                 // by="word"
const hidden = { opacity: 0, y: "-0.5em" };     // directionOffset("up")
return createElement(Tag, { "aria-label": text }, tokens.map((t, i) => (
  <m.span key={i} aria-hidden="true" className="inline-block whitespace-pre-wrap"
    initial={hidden} animate={{ opacity: 1, x: 0, y: 0 }}
    transition={{ duration: FADE, ease: REVEAL_EASE, delay: delay + i * stagger }}>{t}</m.span>
)));
```

Optional scroll cue (ChevronDown) loops only AFTER the hero settles: `delay = D_ACTIONS + FADE + 0.2`.

---

## 5. GRID STAGGER = ONE container trigger, never per-card index*delay (the stale-delay bug)

The single most common motion bug. For any grid/list of cards (team, services, projects),
put `whileInView` + `viewport` on the PARENT container with `staggerFast`; children declare
only `variants={fadeUp}` and NO `whileInView` of their own.

```tsx
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
// LaptopShowcase — pre-warm + dual trigger
useEffect(() => { void import("./LaptopScene"); }, []);                 // kick the network fetch now
const nearView = useInView(sectionRef, { margin: "0px 0px -120px 0px", once: true });
// + a requestIdleCallback(…, { timeout: 1000 }) ~800ms after mount sets idleWarmed
const showScene = nearView || idleWarmed;                              // whichever fires first
if (!isDesktop) return <MobileLaptopFallback />;                       // CSS/DOM mock, no WebGL on phones
const LaptopScene = dynamic(() => import("./LaptopScene"),
  { ssr: false, loading: () => <HeroSceneSkeleton /> });               // reserve space, no CLS
```

```tsx
// LaptopScene — on-demand render; only repaints on scroll/warm-up, not 60fps at rest
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

## 8. SWR data layer (`useQuery`) — in-memory + sessionStorage tiers + inflight dedup

Serve cached instantly, revalidate in the background, never refetch the same key twice in
parallel. Whitelist stable keys for sessionStorage so hard reloads paint sub-1s from cache.

```ts
useQuery<T>(key, fetcher, { ttl = 2*60_000, refetchInterval, enabled = true })
//  → in-memory cache serves first (loading=false if hit)
//  → if cache.isStale(key, ttl) → silent background refetch
//  → cache.promotePersisted(key) lifts whitelisted keys (e.g. "account","projects") from sessionStorage
//  → setInflight(key, promise) dedups concurrent callers onto ONE promise
//  → cache.subscribe(key, …) propagates external cache.set(key, data) without a refetch
```

Tier TTLs by volatility: static content ≈ infinite, semi-static minutes/hours, volatile short.
Prefer server-side fetch for first paint; fire independent requests together (no waterfall
where one query's input depends on a prior query's output). Reserve `force-dynamic` for
genuinely per-request auth-gated pages.
