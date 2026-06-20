# Project-specific conventions

Rules and patterns established for this project (or, when promoted, for all future builds). The agent reads this at the start of every phase and applies the rules.

## Format

```
## <category> — <rule name>

<the rule, stated as a directive — "Always X" / "Never Y" / "When A then B">

**Rationale:** <why>
**Established:** YYYY-MM-DD
**Source:** correction from user | self-observed failure | initial setup
```

## Active conventions

<!-- Append entries below this line. Group by category if it helps (Typography, Layout, Motion, SEO, A11y, Testing). -->

## Starter rules (apply to all builds)

### Imports — Motion library naming

Always import Motion from `motion/react`, never from `framer-motion`. The package was renamed in mid-2025.

**Rationale:** The legacy `framer-motion` package still works but receives no updates. The new `motion` package is actively maintained.
**Established:** initial setup
**Source:** initial setup

### Imports — i18n library

Always use `next-intl` for internationalization, never `next-i18next` or `react-i18next`.

**Rationale:** `next-intl` is the de facto i18n library for Next.js App Router with full RSC support. The others either don't work with App Router (`next-i18next`) or don't integrate with Next's routing system (`react-i18next`).
**Established:** initial setup
**Source:** initial setup

### Routing — locale prefix

Every page lives under `app/[locale]/`. Even single-locale projects use the locale prefix — it makes adding new locales later trivial.

**Rationale:** Avoids painful migrations later when the user decides to add another market.
**Established:** initial setup
**Source:** initial setup

### Translation — CMS-sourced, seed files as pre-connection fallback

Non-default locale `messages/<locale>.json` files are **build-time seeds / pre-connection fallbacks**. The default-locale file holds real copy; non-default seed files mirror it (same values — no `[XX]`/`[NL]` placeholders to hand-maintain).

Once the site is connected to the CMS (CMS Connector agent sets `NEXT_PUBLIC_CMS_ENDPOINT`), `i18n/request.ts` loads messages live from the CMS per locale. The CMS auto-translates the default locale into the others (DeepL when configured, else echoes the source). No separate translation pipeline is needed.

**Rationale:** Placeholders caused visible garbage text in QA and required a manual translation step. The CMS handles translation automatically post-connection; seeds keep the site functional before that point.
**Established:** 2026-06-06
**Source:** user instruction

### Metadata — viewport export separation

In `app/layout.tsx`, `themeColor`, `width`, and `initialScale` go in the `viewport` export, NOT in the `metadata` export.

**Rationale:** Breaking change since Next.js 15. Putting them in `metadata` produces a warning and is silently ignored.
**Established:** initial setup
**Source:** initial setup

### Images — never raw img tags

Use `next/image` for every image except inside `next/og` ImageResponse. Always include `alt`, `width`, `height` (or `fill` with sized parent), and `sizes` for non-priority images.

**Rationale:** Performance (CLS, LCP) and a11y.
**Established:** initial setup
**Source:** initial setup

### Output location

The agent generates new sites as siblings to "CMS - websites" at `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`, never nested inside the CMS repo.

**Rationale:** Keeps each generated site independently versionable and deployable.
**Established:** initial setup
**Source:** user instruction

### Routing — root layout lives in `app/[locale]/layout.tsx`

Make `app/[locale]/layout.tsx` the ROOT layout: it renders `<html>`/`<body>`. Do NOT keep a pass-through `app/layout.tsx` that just returns `{children}`.

**Rationale:** Next 16 errors "Missing `<html>` and `<body>` tags in the root layout" — a redundant `app/layout.tsx` wrapper either duplicates or strips the html/body the App Router expects on the topmost layout.
**Established:** 2026-06-17
**Source:** self-observed failure

### Hydration — browser-translation resilience (every multilingual site)

On every multilingual site, ship two things: (1) a tiny `beforeInteractive` shim that patches `Node.prototype.removeChild` + `insertBefore` so that when `child.parentNode !== this`, `removeChild` detaches the node from its ACTUAL parent and returns it, and `insertBefore` APPENDS the node to the intended parent instead of throwing; (2) `suppressHydrationWarning` on `<html>`. Do NOT patch `replaceChild` (React 19 never calls it).

**Rationale:** In-browser translators (Google/Chrome auto-translate) reparent text nodes into `<font>` wrappers and mutate `<html lang>`/class. React's commit phase then calls the native `removeChild`/`insertBefore` against the original parent, the call throws `NotFoundError`, and with no error boundary React escalates to a FULL root unmount — interactive components (e.g. the booking form) vanish on the next re-render. The shim keeps the page translatable into any language without crashing; `suppressHydrationWarning` also silences next/font's Turbopack-dev hash mismatch. Real users who don't translate are unaffected.
**Established:** 2026-06-17
**Source:** self-observed failure

### Layout — responsive selectable cards (avatar | text | pill)

When a selectable card is laid out `avatar | text | pill` with a fixed `Select`/`Selected` pill (`flex:0 0 auto`), on phones collapse the pill to a compact ICON-ONLY badge (check/plus), hide its text label, and put `min-width:0` on the text column. Keep the labelled pill on desktop. The whole card is the tap target.

**Rationale:** A non-shrinking pill crushes the text column to ~one word per line and visually overlaps the text on phones.
**Established:** 2026-06-17
**Source:** self-observed failure

### Layout — confirmation/success screens fit every viewport

Confirmation/success screens must fit FULLY without scrolling on EVERY viewport (verify 320→1440). Use a compact centred layout, `@media (max-height: …)` tiers that progressively shrink type + spacing on short screens, and on genuinely tiny legacy phones (`≤360w AND ≤600h`) drop ONLY the least-important secondary line. Animate the success checkmark — never pop it.

**Rationale:** A confirmation the user has to scroll to read feels broken; short-viewport phones otherwise clip the action/checkmark below the fold.
**Established:** 2026-06-17
**Source:** self-observed failure

### Motion — inter-page route loader uses a dedicated localized line

The route-segment loader (`app/[locale]/loading.tsx`) is a first-class, full-screen-capable themed splash: brand wordmark + spinner + a SHORT, business-flavoured status line from a DEDICATED i18n key (`loader.routeLoading`) — never reuse the intro loader's loading copy. Theme to the palette, z-index ABOVE the header + mobile menu, respect reduced-motion.

**Rationale:** A small in-content spinner reads as a glitch between pages; a dedicated key keeps the inter-page copy distinct from the first-load intro and translatable per locale.
**Established:** 2026-06-17
**Source:** self-observed failure

<!-- ── Motion & Performance Standards (promoted 2026-06-17 from the CMS frontend's
     Akris-inspired motion/perf pass). Fast + tastefully animated by default.
     Complements "Imports — Motion library naming" and "Motion — inter-page route loader" above. ── -->
<!-- REFERENCE IMPLEMENTATION: the concrete, copy-usable patterns that realize the rules below
     (provider stack, page-change spinner, header/hero/grid motion, 3D, SWR) live in
     `learnings-template/frontend-patterns.md`. Read THAT for real component code + token
     values; the entries below are the rules + budgets. Keep this file a rule list. -->

### Motion — one shared token set, reused everywhere

Define the easing curve, base durations, and travel distances ONCE (e.g. `REVEAL_EASE = [0.16, 1, 0.3, 1]`, entrances 0.4–0.6s, travel 16–40px) and reuse them via primitives (`Reveal`, `TextReveal`, a slide-in factory, a stagger container). Never hand-write ad-hoc inline `transition`/`initial` objects per component.

**Rationale:** A site reads as "intentional" when every reveal/transition feels identical, and as "AI slop" when each component invents its own ease/duration.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Motion — LazyMotion + `m` contract (one app-level provider)

Use the tree-shakeable runtime (`LazyMotion features={domAnimation}` + the `m` component), but provide exactly ONE app-level `LazyMotion` provider near the root so `m` components always have an ancestor. Do NOT use `strict` if any full `motion` components are also used (strict rejects them).

**Rationale:** An `m` component rendered outside a `LazyMotion` ancestor silently no-ops — it ships dead markup and the section looks broken in subtle ways. One root provider makes it impossible to forget.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Motion — global reduced-motion

Wrap the app in a single `MotionConfig reducedMotion="user"` near the root, and in any bespoke scroll/RAF/3D code add an explicit static fallback (lock to a sensible final state, skip loops).

**Rationale:** Accessibility is non-negotiable; centralizing it prevents per-component drift.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Motion — scroll-triggered reveals are the workhorse (with restraint)

Entrances = fade + small directional travel (16–40px), ease-out, fire ONCE on viewport entry (`whileInView` + `viewport={{ once: true }}`). Keep durations 0.3–0.6s and stagger children slightly (next beat starts before the previous finishes). Animate 1–2 key elements per view max — section header + its primary block/grid — never every element.

**Rationale:** Large travel/long durations read as sluggish; blanket-animating everything reads as AI-generated. Spend boldness on the hero signature, keep the rest quiet.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Motion — page transitions are opacity-only when sticky scenes exist

For route transitions use an opacity-only cross-fade (`AnimatePresence mode="wait"`, exit faster than enter). NEVER apply transform/scale/blur to the transition wrapper if the page contains `position: sticky`/`fixed` scroll scenes — a transformed/blurred ancestor establishes a containing block that breaks them.

**Rationale:** A blurred/transformed ancestor silently breaks sticky/fixed descendants (e.g. a tall sticky 3D showcase); opacity does not, and is the cheapest GPU-friendly cross-fade.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Performance — thin client boundary + lazy heavy modules

Keep `'use client'` at provider/island level so server components render most HTML. Lazy-load heavy or below-the-fold interactive modules (3D, charts, video) with `next/dynamic` `ssr:false` + a skeleton fallback that reserves space (no layout shift). Pre-warm the chunk on idle and mount on viewport-intersection so it never blocks first paint or the hero intro.

**Rationale:** Heavy modules in the initial/critical path delay TTI and can hitch the hero animation.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Performance — viewport-aware / on-demand render loops

Run continuous animation (RAF / WebGL frameloop / scroll-scrub) only while the section is near the viewport; freeze when away. Prefer on-demand rendering (`frameloop="demand"` + `invalidate()` on input change) over always-on so static end-states stop repainting identical frames. Channel scroll-linked work through a SINGLE RAF loop (e.g. drive smooth-scroll and motion off one frame loop).

**Rationale:** Always-on loops and competing RAF loops waste GPU/CPU and fight for the main thread, making the whole page feel slow.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Performance — 3D/WebGL hero rules

Cap `devicePixelRatio` (~1.5), bake the environment/reflections procedurally instead of fetching an HDR (no network failure mode), warm shaders/geometry ~200ms after mount (so it appears with no cold-start hitch), and ALWAYS provide a static CSS/image fallback on mobile so WebGL never loads on small/low-power devices.

**Rationale:** Keeps an impressive 3D hero off the critical path and off low-power devices entirely.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass

### Performance — SWR data layer + server-first fetch

Default to stale-while-revalidate with in-flight de-duplication and content-tiered freshness (static ≈ infinite, semi-static minutes/hours, volatile short TTL): serve cached instantly, revalidate in the background. Prefer server-side fetching for first paint; kick off independent requests together and avoid client fetch waterfalls (watch for a query whose input depends on a prior query's output). Reserve `force-dynamic` for genuinely per-request auth-gated pages.

**Rationale:** Redundant requests and client-side waterfalls are the cheapest perf regressions to avoid on a content site.
**Established:** 2026-06-17
**Source:** promoted — CMS frontend motion/perf pass
