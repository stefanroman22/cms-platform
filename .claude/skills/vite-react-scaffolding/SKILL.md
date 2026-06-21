---
name: vite-react-scaffolding
description: Set up a new Vite 7 + React 19 SPA with build-time SSG pre-rendering (vite-react-ssg), React Router v7 (library mode), Tailwind v4, shadcn/ui, Motion, TanStack Query (localStorage-persisted), Zustand (persist), and Playwright. Use whenever scaffolding a new site from scratch. Triggers on "scaffold the project", "set up the app", "create the new site".
---

# Vite + React SPA Scaffolding (SSG)

## Scaffold sequence (Windows / PowerShell; cd to the parent scratch dir FIRST)

1. `npm create vite@latest <folder> -- --template react-ts`
2. `cd <folder>`
3. **Pin Vite 7 immediately** (before any other installs — `npm create vite@latest` now scaffolds Vite 8, which exceeds vite-react-ssg's `vite@^7` peer cap and causes ERESOLVE on the next step):
   `npm install -D vite@^7 @vitejs/plugin-react@^4`
4. Install runtime deps:
   `npm i react-router-dom react-i18next i18next i18next-browser-languagedetector @tanstack/react-query @tanstack/react-query-persist-client @tanstack/query-sync-storage-persister zustand motion lucide-react`
5. Create `.npmrc` in the project root with `legacy-peer-deps=true` (makes `npm ci` sticky for CI; required because vite-react-ssg 0.9.0 declares `react-router-dom@^6.14.1` as peerOptional, conflicting with RR v7):
   ```
   legacy-peer-deps=true
   ```
6. Install build/SSG + SEO-gen deps (use `--legacy-peer-deps` and pin vite-react-ssg to stable 0.9.0 — npm `latest` tag points at a `0.9.1-beta.1` prerelease):
   `npm i -D vite-react-ssg@0.9.0 satori @resvg/resvg-js sharp @playwright/test @axe-core/cli --legacy-peer-deps`
7. **Add patch-package** (persists the react-router-dom/server.js shim across fresh installs — see "RR7 compatibility shim" below):
   `npm i -D patch-package --legacy-peer-deps`
   Then add `"postinstall": "patch-package"` to `package.json` scripts.
8. Tailwind v4: `npm i -D tailwindcss @tailwindcss/vite` and add the plugin to `vite.config.ts` (NOT a PostCSS config). Import `tailwindcss` in `src/index.css` via `@import "tailwindcss";`.
6. shadcn/ui (Vite mode): `npx shadcn@latest init` then add primitives as needed (`npx shadcn@latest add button ...`). Components vendor into `src/components/ui/`.
7. Fonts: install the chosen families via `@fontsource`/`@fontsource-variable` (e.g. `npm i @fontsource-variable/fraunces`) and `import` them in `src/index.css`. NEVER `next/font`.

## package.json scripts

- `"dev": "vite"`
- `"build": "vite-react-ssg build"`     # pre-renders every route × locale
- `"preview": "vite preview"`
- `"prebuild": "tsx src/seo/sitemap.gen.ts && tsx src/seo/robots.gen.ts && tsx src/seo/og.gen.ts"`
- `"test:e2e": "playwright test"`

## Canonical folder structure

```
<business>/
  index.html                     # inline translation-shim <script>; SPA mount; head base
  vite.config.ts                 # React plugin, vite-react-ssg, manualChunks, alias @/*
  src/
    main.tsx                     # ssg entry (createRoot/hydrate via vite-react-ssg)
    routes.tsx                   # React Router v7 route table (locale-prefixed, React.lazy)
    i18n/
      config.ts                  # react-i18next init, resources, fallbackLng
      messages/<locale>.json     # namespaced t() keys (CMS merges over these — UNCHANGED shape)
    pages/                       # one component per route (was app/[locale]/<route>/page.tsx)
    components/sections/<name>.tsx
    components/RouteLoader.tsx    # themed splash as Suspense fallback (was loading.tsx)
    lib/
      config.ts                  # SITE_URL, SUPPORTED_LOCALES, DEFAULT_LOCALE
      cms-content.ts             # build-time + client merge of CMS payload over messages
      cms-site.ts                # resolveSite() — UNCHANGED contract
      seo-meta.ts                # build-time fetch of stored seo_page_meta (no ISR)
      query.ts                   # QueryClient + localStorage persister
      store.ts                   # Zustand stores (persist): locale, booking, ui
      head.ts                    # per-route×locale head builder (React 19 hoisted tags)
    seo/
      sitemap.gen.ts             # prebuild → public/sitemap.xml
      robots.gen.ts              # prebuild → public/robots.txt
      og.gen.ts                  # prebuild → public/og/*.png (satori + sharp)
  public/images/<section>/       # mock images, copied as-is (UNCHANGED rule)
  .learnings/                    # per-build corrections (UNCHANGED)
  package.json                   # vite, react@19, react-router, react-i18next, @tanstack/*, zustand, motion, tailwind, playwright
```

## vite.config.ts (shape)

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: { alias: { "@": path.resolve(__dirname, "src") } },
  build: {
    rollupOptions: {
      output: {
        manualChunks: {
          react: ["react", "react-dom", "react-router-dom"],
          query: ["@tanstack/react-query"],
          motion: ["motion"],
        },
      },
    },
  },
  // vite-react-ssg options (ssgOptions is a top-level config key, not inside build)
  ssgOptions: {
    entry: "src/main.tsx",      // REQUIRED — default is src/main.ts (no x); must override
    formatting: "none",         // valid values: 'prettify' | 'none' — 'minify' is NOT valid in 0.9.0;
                                // 'prettify' can break hydration — use 'none'
    dirStyle: "nested",         // emits dist/<locale>/index.html (clean /en/ URLs); default is 'flat'
    onPageRendered(route, html) {
      // vite-react-ssg does NOT rewrite the static lang="en" baked into index.html,
      // and React 19 cannot hoist attributes onto the existing <html> element.
      // Extract the locale from the route path (e.g. "/en" → "en", "/nl/about" → "nl").
      const locale = route.split("/").find((seg) => seg.length === 2) ?? "en";
      return html.replace(/<html([^>]*) lang="[^"]*"/, `<html$1 lang="${locale}"`);
    },
  },
});
```

## RR7 compatibility shim (patch-package)

vite-react-ssg 0.9.0 does `await import('react-router-dom/server.js')` during the SSG render
stage. React Router v7 **removed the `./server.js` subpath** — those APIs now live in the main
entry — so SSG dies with `ERR_PACKAGE_PATH_NOT_EXPORTED`. Persist a shim via patch-package:

1. Create `node_modules/react-router-dom/server.js`:
   ```js
   // react-router-dom/server.js — RR7 moved these to the main entry; vite-react-ssg still imports the v6 subpath
   export { createStaticHandler, createStaticRouter, StaticRouterProvider } from "react-router-dom";
   ```
2. Add `"./server.js": "./server.js"` to the `exports` map in `node_modules/react-router-dom/package.json`.
3. Run `npx patch-package react-router-dom` — this writes `patches/react-router-dom+<ver>.patch`.
4. Commit `patches/` to version control. The `postinstall` hook re-applies it on every fresh `npm install`.

Track vite-react-ssg for native RR7 support to retire this patch later.

## SSG entry (vite-react-ssg)

`src/main.tsx` exports the routes for `vite-react-ssg` and lists the locale × route params to
pre-render (the `getStaticPaths` equivalent). Each pre-rendered HTML carries localized content
+ head tags in the raw markup.

The package exports **`ViteReactSSG`** (NOT `ViteSSG`). Its signature is
`ViteReactSSG(routerOptions, fn?, clientOptions?)` where arg 1 is a `{ routes }` **object**
(not a bare array). Canonical `src/main.tsx`:

```ts
import "./i18n/config";                // init i18next (side effect)
import { ViteReactSSG } from "vite-react-ssg";
import { routes } from "./routes";

// ViteReactSSG consumes { routes } — NOT a bare array, NOT ViteSSG.
export const createRoot = ViteReactSSG({ routes });
```

Keep the Vite default mount `<div id="root">` in `index.html` so no `rootContainer` override is needed.

## Translation-resilience shim

In `index.html`, the FIRST `<script>` (before the module script) patches
`Node.prototype.removeChild`/`insertBefore` (when `child.parentNode !== this`, operate on the
real parent instead of throwing). Do NOT patch `replaceChild`.

## Data cache + app state (localStorage)

- `src/lib/query.ts` — a `QueryClient` wrapped with `persistQueryClient` +
  `createSyncStoragePersister({ storage: window.localStorage })`. Used for CMS content, SEO
  prose, booking availability (stale-while-revalidate).
- `src/lib/store.ts` — Zustand stores with `persist` middleware (localStorage): `useLocaleStore`,
  `useBookingStore` (service/staff/date/weekOffset), `useUiStore` (menuOpen, theme).

## Performance defaults

Route-level `React.lazy` per page; `manualChunks` vendor split; Vite dep pre-bundling +
persistent `node_modules/.vite` cache (do not delete between builds).

## Mock image organization

Files copied from the design go into `public/images/<section>/`. The section name should match the section in `_design-manifest.json`. Always reference via `<img>` with `srcset`/`sizes` (or a small `<Image>` wrapper component). NEVER `next/image`.

## Common scaffolding pitfalls to avoid

- Running `npm create vite` from inside "CMS - websites" — always `cd` to the parent scratch directory first.
- Skipping `npm install` thinking it's not needed yet — TypeScript checks fail without it.
- Installing `framer-motion` — wrong package. Always `npm install motion`.
- Installing `next-intl` or `next-i18next` — wrong package. Always `react-i18next` + `i18next`.
- Forgetting to copy `agents/Website Builder/learnings-template/*` into `.learnings/` — the agent then has no place to log corrections.
- Leaving the placeholder `SITE_URL = "https://example.com"` — replace with the real domain (or ask the user) before final build.
- Deleting `node_modules/.vite` between builds — this cache is Vite's dep pre-bundle; keep it.

## Hard rules

- NEVER `create-next-app`, `app/` router, `next.config`, `middleware.ts`, `next/font`,
  `next/image`, `generateMetadata`. This is a Vite SPA.
- Locale lives in the URL segment (`/:locale/...`) via React Router; every page nests under it.
- Use `<img>` with `srcset`/`sizes` (or a small `<Image>` wrapper), not `next/image`.
