# Phase 3 — Scaffold

**Apply skills:** `vite-react-scaffolding` + `i18n-setup`.

**Do:**
- `cd` to the parent scratch directory FIRST, then `npm create vite@latest <folder> -- --template react-ts`.
- Install runtime deps: `react-router-dom`, `react-i18next`, `i18next`,
  `i18next-browser-languagedetector`, `@tanstack/react-query`,
  `@tanstack/react-query-persist-client`, `@tanstack/query-sync-storage-persister`, `zustand`,
  `motion`, `lucide-react`.
- Install build/SSG + SEO-gen dev deps: `vite-react-ssg`, `satori`, `@resvg/resvg-js`, `sharp`,
  `@playwright/test`, `@axe-core/cli`, `tailwindcss`, `@tailwindcss/vite`.
- Wire react-i18next: create `src/i18n/config.ts` (init with resources, fallbackLng, supportedLngs)
  and `src/i18n/messages/<locale>.json` seed files mirroring the default locale — no
  `[XX]`/`[NL]` placeholders. Locale lives in the URL segment (`/:locale/...`) via a React Router
  parent route + a `<LocaleGuard>` component that validates the segment and calls
  `i18n.changeLanguage(locale)`. Once the site is connected to the CMS (`VITE_CMS_ENDPOINT` set),
  content loads live per locale and the CMS auto-translates the default locale into the others.
  See `i18n-setup` skill for full wiring details.
- Set up `src/lib/query.ts` (QueryClient wrapped with `persistQueryClient` +
  `createSyncStoragePersister({ storage: window.localStorage })`) and `src/lib/store.ts`
  (Zustand stores with `persist` middleware: `useLocaleStore`, `useBookingStore`, `useUiStore`).
- Fonts via `@fontsource*` / `@fontsource-variable` packages; `@import` them in `src/index.css`.
  Tailwind v4 via `@tailwindcss/vite` plugin in `vite.config.ts` (NOT PostCSS);
  `@import "tailwindcss";` in `src/index.css`.
- Add the translation-resilience shim as the FIRST inline `<script>` in `index.html` (before
  the module script): patch `Node.prototype.removeChild`/`insertBefore` when
  `child.parentNode !== this` to operate on the real parent instead of throwing. Do NOT patch
  `replaceChild`. Add `suppressHydrationWarning` on `<html>`.
- Create the canonical `src/` folder structure from `vite-react-scaffolding` (`main.tsx`,
  `routes.tsx`, `i18n/`, `pages/`, `components/sections/`, `components/RouteLoader.tsx`,
  `lib/{cms-content,cms-site,seo-meta,query,store,head}.ts`,
  `seo/{sitemap,robots,og}.gen.ts`).
- Copy the design's mock images to `public/images/<section>/<filename>`.
- Copy `agents/Website Builder/learnings-template/*` into the new project's `.learnings/`.
- If `ui-ux-pro-max` is installed, run its design-system generator and reconcile with the
  manifest tokens — the design wins on direct conflicts; ui-ux-pro-max fills gaps.

**Gate:** `npm run dev` boots (Vite dev server); `/` redirects to `/<default-locale>` via
React Router; `.learnings/` has all three template files; mock images are in place;
`src/lib/query.ts` and `src/lib/store.ts` exist; `index.html` first `<script>` is the
translation shim.

**Token tactics:** don't echo full `npm create vite` output; summarize success/failure.
