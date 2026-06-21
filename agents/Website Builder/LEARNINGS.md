# Website Builder — LEARNINGS

Append-only cross-build meta-lessons for the website-builder agent. Phase 8 adds at least one
generalizable lesson per build. The subagent reads this file at startup only if it exceeds 25
lines (the empty scaffold is skipped to save tokens).

## Format

```
## YYYY-MM-DD — <one-line lesson>

**Build:** <which site / design>
**Lesson:** <the generalizable takeaway>
**Apply:** <how future builds should change>
```

## Entries

<!-- Append below. Newest at the top. -->

## 2026-06-21 — Validated Vite+React19 SSG build; pinned the working stack

**Build:** Lumière Bistro dry-run (French bistro, Antwerp — PoC to validate the SSG stack)
**Lesson:** Build exit 0 confirmed: per-locale raw-HTML pre-render (EN + NL), localized content +
hoisted `<title>`/`<meta>`, full hreflang sets, and localStorage wiring (TanStack Query persister
+ Zustand persist) all verified via a real dry-run. BUT the stack as documented did NOT install
cleanly on current npm dist-tags — 3 ERESOLVE failures + 1 hard runtime crash were hit and fixed.
WORKING pins and workarounds (all now in the updated vite-react-scaffolding skill):
- **Vite ^7**: `npm create vite@latest` scaffolds Vite 8 (exceeds vite-react-ssg `vite@^7` peer
  cap); pin immediately after scaffold with `npm install -D vite@^7 @vitejs/plugin-react@^4`.
- **vite-react-ssg@0.9.0**: npm `latest` tag points at `0.9.1-beta.1` prerelease; pin stable.
- **.npmrc `legacy-peer-deps=true`** + `--legacy-peer-deps` on SSG install: vite-react-ssg 0.9.0
  declares `react-router-dom@^6.14.1` peerOptional, conflicts with mandated RR v7.
- **patch-package `react-router-dom/server.js` shim**: vite-react-ssg imports the v6
  `react-router-dom/server.js` subpath that RR7 removed (`ERR_PACKAGE_PATH_NOT_EXPORTED`).
  Shim content: `export { createStaticHandler, createStaticRouter, StaticRouterProvider } from "react-router-dom";`
  + `"./server.js": "./server.js"` in RR's `exports` map. Run `npx patch-package react-router-dom`
  to persist under `patches/`; add `"postinstall": "patch-package"` to scripts. Track vite-react-ssg
  for native RR7 support to retire later.
- **`ViteReactSSG({ routes })`**: export name is `ViteReactSSG` (NOT `ViteSSG`); arg 1 is a
  `{ routes }` object not a bare array.
- **`ssgOptions`**: `entry: "src/main.tsx"` (default is `.ts`), `formatting: "none"` (only
  `'prettify' | 'none'` are valid; `'prettify'` breaks hydration; `'minify'` is invalid),
  `dirStyle: "nested"` (emits `dist/<locale>/index.html` for clean `/en/` URLs).
- **`onPageRendered` for `<html lang>`**: vite-react-ssg does not rewrite the static `lang="en"`
  in index.html; React 19 cannot hoist onto existing `<html>`. Use `ssgOptions.onPageRendered`
  to string-replace `<html lang="...">` with the route's locale segment.
**Apply:** Scaffold per the updated `vite-react-scaffolding` skill — these pins are mandatory.

## 2026-06-20 — Builder now emits Vite + React 19 (SSG), not Next.js

**Lesson:** From-scratch builds are Vite 7 + React 19 SPAs pre-rendered by vite-react-ssg
(React Router v7 library mode, react-i18next, TanStack Query + Zustand persisted to
localStorage). SEO moves from `generateMetadata`/ISR to build-time head hoisting + prebuild
sitemap/robots/OG + a build-snapshot-plus-client-refetch freshness model. The old "never use
localStorage" rule is SUPERSEDED — localStorage is now first-class. The Next-root-layout lesson
below is obsolete for new builds.

**Apply:** Scaffold via `vite-react-scaffolding`; never `create-next-app`/`app/`/`next-intl`/
`generateMetadata`.

## 2026-06-17 — Shim Node.removeChild/insertBefore so in-browser translators can't crash React

**Build:** samir-kapsalon
**Lesson:** In-browser translators (Google Translate / Chrome auto-translate) rewrite the live
DOM — wrapping text nodes in `<font>` elements (reparenting them) and mutating `<html lang>`/class.
React's commit phase then calls `parent.removeChild(node)` / `parent.insertBefore(node, ref)`
against the ORIGINAL parent; the native call throws `NotFoundError`, and with NO error boundary
React escalates it to a full ROOT UNMOUNT — interactive components (e.g. the booking form) vanish
on the next re-render (switching barber, etc.). The lang/class "hydration mismatch" warnings share
this cause.
**Apply:** Add a tiny `beforeInteractive` shim patching `Node.prototype.removeChild` +
`insertBefore`: when `child.parentNode !== this`, `removeChild` detaches the node from its ACTUAL
parent (so stale text doesn't linger) and returns it; `insertBefore` APPENDS `newNode` to the
intended parent (so it isn't silently dropped, blanking the UI) instead of throwing. React 19
never calls `replaceChild` — do NOT patch it. Also set `suppressHydrationWarning` on `<html>`
(covers the translator's lang/class mutation AND next/font's Turbopack-dev hash mismatch). Page
stays translatable into any language without crashing; non-translating users are unaffected.

## 2026-06-17 — In Next 16, app/[locale]/layout.tsx IS the root layout — no pass-through app/layout.tsx

**Build:** samir-kapsalon
**Lesson:** The topmost layout must render `<html>`/`<body>`. For the i18n `app/[locale]/` pattern,
keeping a pass-through `app/layout.tsx` that just returns `{children}` makes Next 16 error
"Missing `<html>` and `<body>` tags in the root layout".
**Apply:** Make `app/[locale]/layout.tsx` the ROOT layout (it renders `<html>`/`<body>`); do NOT
keep an `app/layout.tsx`.

## 2026-06-17 — Booking-UI refinements: week-paginated picker, selection cross-fade, icon-only pill, no-scroll success, themed route loader

**Build:** samir-kapsalon
**Lesson:** A Fresha/Treatwell-style flow (Services → Professional → Time → Confirm; sticky
right-column action card on desktop, sticky bottom bar on mobile) needs several refinements the
defaults miss: (a) a long horizontally-scrolling date strip should be a FIXED 7-day week —
prev/next arrows on the RIGHT of the "Pick a day" header, back disabled on week 0 (today),
forward +7 up to ~6 months, sold-out days greyed/disabled, availability fetched lazily per visible
week and reset to week 0 when service/barber changes, cells `grid repeat(7,1fr)` so they always
fit with no h-scroll, week change = directional `AnimatePresence` slide keyed on the offset
(reduced-motion → fade); (b) selectable service/barber cards should cross-fade between stacked
"+" and "check" icons (opacity + scale) as colour/border transitions — not pop; (c) an
"avatar | text | pill" card where the pill is `flex:0 0 auto` crushes the text on phones — collapse
the pill to an ICON-ONLY badge on mobile (whole card is the tap target), `min-width:0` on the text
column, labelled pill on desktop; (d) the success screen must fit with NO scroll on every viewport
(verified 320→1440) via `@media (max-height)` tiers and dropping only the least-important line on
tiny legacy phones (`<=360w AND <=600h`) — and "manage your booking" must be its OWN themed
hover-able accent link, distinct from the "Date & time" detail label.
**Apply:** Animate selection/check-marks (never pop); paginate date pickers by week instead of
scrolling; make pills icon-only on mobile; pressure-test confirm/success screens at min/short
viewports. Elevate the route loader (`app/[locale]/loading.tsx`) to a first-class themed splash —
brand wordmark + spinner + a SHORT business-flavoured status line via a DEDICATED i18n key
(e.g. `loader.routeLoading`, NL "Bezig met knippen…" / EN "Cutting in progress…"), NOT the intro
loader's copy; theme to the palette, z-index above header & mobile menu, respect reduced-motion.

## 2026-05-22 — Point Playwright's webServer at a production build in sandboxed runs

**Build:** samir-kapsalon
**Lesson:** The default `playwright-user-stories` config runs `npm run dev` as the webServer.
In this sandbox that fails (dev HMR stalls hydration — see the earlier entry), so client-
interaction tests never pass. Setting `webServer.command` to `npx next start -p <port>` (after
a build) gave a clean run: 42/42 passed including the booking-flow interaction.
**Apply:** For Phase 7, when the environment can't run dev HMR, configure Playwright's webServer
to serve a production build. Also: Pixel-family devices are Chromium (only `chromium` is usually
installed); iPhone descriptors pull WebKit and fail to launch unless `playwright install webkit`.

## 2026-05-22 — getByRole name match is substring + case-insensitive — use exact for short labels

**Build:** samir-kapsalon
**Lesson:** A language-switch test for the "EN" button also matched the "Open m**en**u" hamburger
(visible only at mobile widths), causing a strict-mode violation on the mobile project only.
**Apply:** For 2-letter / short accessible names (EN, NL, OK), use
`getByRole(role, { name, exact: true })` to avoid accidental substring matches.

## 2026-05-22 — Verify hydration on a production server, not the dev server, in sandboxed/headless browsers

**Build:** samir-kapsalon (Claude Design barbershop)
**Lesson:** In this environment the Playwright/MCP browser cannot complete Next.js dev's HMR
WebSocket handshake (`ws://.../_next/webpack-hmr` → ERR_INVALID_HTTP_RESPONSE). That stalls
client hydration in `next dev`, so client effects (scroll-state header, IntersectionObserver
reveals) never run — looking like a real bug when it isn't. `npm run build` + `next start`
(no HMR) hydrates correctly and is the source of truth for client-behavior checks.
**Apply:** During Phase 6/7, when client interactivity "doesn't work" under Playwright, first
rule out the dev HMR artifact by testing against a production server before changing code.

## 2026-05-22 — Gate scroll-reveal hidden state behind an `html.js` class

**Build:** samir-kapsalon
**Lesson:** Designs that default `.reveal { opacity: 0 }` and rely on JS to add `.is-visible`
leave content invisible for no-JS users/crawlers and look broken in full-page screenshots.
**Apply:** Make the hidden state `html.js .reveal { opacity: 0; ... }` and set
`document.documentElement.classList.add('js')` in an inline script before paint. Content is
visible by default; the reveal is a pure progressive enhancement.

## 2026-05-22 — Self-host fonts the brief names even when they're not on Google Fonts

**Build:** samir-kapsalon (Anton display + Switzer body)
**Lesson:** Switzer (the brief's body font) is on Fontshare, not Google Fonts. Fetched the 4
weight woff2 files from the Fontshare CDN (protocol-relative `//cdn.fontshare.com/...` URLs)
and wired them via `next/font/local`. Anton came from `next/font/google`.
**Apply:** Don't substitute a Google "close enough" font when the brief names a specific one —
download the woff2s and self-host with next/font/local to stay faithful and avoid the AI-default
font ban.
