# Website Builder → Vite + React 19 — Plan A (Builder Core + Skills)

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the website-builder agent and its bundled skills so every from-scratch build produces a Vite + React 19 SPA with build-time SSG pre-rendering, localStorage-backed caching/state, instead of a Next.js 16 app.

**Architecture:** Vite 7 + React 19; `vite-react-ssg` pre-renders each route × locale to static HTML (crawler SEO baseline); React Router v7 (library mode) with locale-prefixed routes; react-i18next keeping the `t()` + `messages/<locale>.json` shape; React 19 native head-tag hoisting + prebuild sitemap/robots/OG; TanStack Query persisted to localStorage for data caching; Zustand `persist` for UI/app state. Live humans get fresh client-refetched content; crawlers get the build snapshot (refreshed by a rebuild-on-publish hook handled in Plan B).

**Tech Stack:** Vite 7, React 19, vite-react-ssg, react-router-dom v7, react-i18next + i18next, @tanstack/react-query + @tanstack/react-query-persist-client, zustand, motion (`motion/react`), shadcn/ui, Tailwind v4, satori + sharp (OG), Playwright.

**Spec:** `docs/superpowers/specs/2026-06-20-website-builder-vite-react-migration-design.md`

## Global Constraints

- These are agent **instruction files** (Markdown) — the deliverable of each doc task is a file that describes the Vite/React/SSG stack with **no remaining Next-only mandates** and **all cross-references resolving**. The executable verification for the whole plan is Task 11 (a real dry-run build).
- **Commits:** per the repo owner's standing rule, do **NOT** auto-commit. Each task's final step **stages** changes (`git add`) and pauses; batch-commit only on Stefan's explicit go-ahead.
- **Stack values (verbatim):** Build tool = Vite 7 + React 19. SSG = `vite-react-ssg`. Router = React Router v7, library mode, locale prefix `/:locale/...`. i18n = `react-i18next` (keep `messages/<locale>.json` namespaced `t()` shape). Data cache = `@tanstack/react-query` + `@tanstack/react-query-persist-client` → localStorage. App state = `zustand` + `persist` → localStorage. Animation = `motion` (`import { motion } from "motion/react"`) — NEVER `framer-motion`. UI = shadcn/ui + Tailwind v4. Tests = Playwright.
- **Carried-over rules (unchanged):** mock images copied as-is to `public/images/<section>/`, never replaced; translation copy is structural (default locale verbatim, `[XX]` placeholders in others); output folder is a sibling `scratch\<business-name>\`, never nested in "CMS - websites"; `.learnings/` is append-only.
- **localStorage:** the old "NEVER use localStorage" prohibition is **removed** and replaced by the TanStack-persist + Zustand-persist model. localStorage is now first-class.
- **SEO guarantee preserved:** every locale is **pre-rendered** (raw-HTML content per locale), so the `content-in-raw-HTML` check still passes — "SSR every locale" becomes "pre-render every locale," same observable result.

## File Structure (Plan A touches)

```
.claude/agents/website-builder.md                         # MODIFY  (stack, hard constraints, skills table, NEVER list)
.claude/skills/vite-react-scaffolding/SKILL.md            # CREATE  (anchor; replaces nextjs-app-scaffolding)
.claude/skills/nextjs-app-scaffolding/                    # DELETE  (retired)
.claude/skills/i18n-setup/SKILL.md                        # MODIFY  (next-intl → react-i18next)
.claude/skills/seo-pro/SKILL.md                           # MODIFY  (Next API → Vite/SSG)
.claude/skills/motion-animations/SKILL.md                 # MODIFY  (one-line descriptor)
.claude/skills/responsive-audit/SKILL.md                  # MODIFY  (next/image note → <img>/srcset)
.claude/skills/playwright-user-stories/SKILL.md           # MODIFY  (baseURL/redirect notes)
agents/Website Builder/AGENTS.md                          # MODIFY  (whole spec)
agents/Website Builder/phases/3-scaffold.md               # MODIFY  (Vite scaffold)
agents/Website Builder/phases/5-seo.md                    # MODIFY  (SSG SEO)
agents/Website Builder/phases/9-incremental.md            # MODIFY  (route-table additive)
agents/Website Builder/learnings-template/conventions.md  # MODIFY  (Vite conventions)
agents/Website Builder/LEARNINGS.md                       # MODIFY  (append migration entry)
```

Skills first (they are the reference docs the agent files point at), then the agent's own
files, then a dry-run build that exercises the whole rewrite.

---

### Task 1: Create the `vite-react-scaffolding` skill (anchor) + retire `nextjs-app-scaffolding`

This skill is the canonical description of the generated project shape. Every other file
references it, so it's built first and in full.

**Files:**
- Create: `.claude/skills/vite-react-scaffolding/SKILL.md`
- Delete: `.claude/skills/nextjs-app-scaffolding/` (entire folder)

**Interfaces:**
- Produces (names later tasks rely on): the canonical folder tree under `src/` (`main.tsx`,
  `routes.tsx`, `i18n/config.ts`, `i18n/messages/<locale>.json`, `pages/`,
  `components/sections/`, `components/RouteLoader.tsx`, `lib/{cms-content,cms-site,seo-meta,query,store,head}.ts`,
  `seo/{sitemap,robots,og}.gen.ts`), the dependency set, the `vite.config.ts` shape, and the
  scaffold command sequence.

- [ ] **Step 1: Read the file being replaced** so the new skill preserves every still-valid idea.

Run: read `.claude/skills/nextjs-app-scaffolding/SKILL.md` end to end. Note which guidance is
stack-agnostic (folder discipline, alias `@/*`, Tailwind, shadcn init, Playwright) vs Next-only
(`create-next-app`, `app/`, `next.config`, `middleware`, `next/font`, `next/image`).

- [ ] **Step 2: Write the new SKILL.md** with this exact frontmatter and content skeleton (fill the prose, but these are the mandated specifics — do not omit any):

```markdown
---
name: vite-react-scaffolding
description: Set up a new Vite 7 + React 19 SPA with build-time SSG pre-rendering (vite-react-ssg), React Router v7 (library mode), Tailwind v4, shadcn/ui, Motion, TanStack Query (localStorage-persisted), Zustand (persist), and Playwright. Use whenever scaffolding a new site from scratch. Triggers on "scaffold the project", "set up the app", "create the new site".
---

# Vite + React SPA Scaffolding (SSG)

## Scaffold sequence (Windows / PowerShell; cd to the parent scratch dir FIRST)

1. `npm create vite@latest <folder> -- --template react-ts`
2. `cd <folder>`
3. Install runtime deps:
   `npm i react-router-dom react-i18next i18next i18next-browser-languagedetector @tanstack/react-query @tanstack/react-query-persist-client @tanstack/query-sync-storage-persister zustand motion lucide-react`
4. Install build/SSG + SEO-gen deps:
   `npm i -D vite-react-ssg satori @resvg/resvg-js sharp @playwright/test @axe-core/cli`
5. Tailwind v4: `npm i -D tailwindcss @tailwindcss/vite` and add the plugin to `vite.config.ts` (NOT a PostCSS config). Import `tailwindcss` in `src/index.css` via `@import "tailwindcss";`.
6. shadcn/ui (Vite mode): `npx shadcn@latest init` then add primitives as needed (`npx shadcn@latest add button ...`). Components vendor into `src/components/ui/`.
7. Fonts: install the chosen families via `@fontsource`/`@fontsource-variable` (e.g. `npm i @fontsource-variable/fraunces`) and `import` them in `src/index.css`. NEVER `next/font`.

## package.json scripts

- `"dev": "vite"`
- `"build": "vite-react-ssg build"`     # pre-renders every route × locale
- `"preview": "vite preview"`
- `"prebuild": "tsx src/seo/sitemap.gen.ts && tsx src/seo/robots.gen.ts && tsx src/seo/og.gen.ts"`
- `"test:e2e": "playwright test"`

## Canonical folder structure

(Reproduce the `src/` tree from the spec verbatim — main.tsx, routes.tsx, i18n/, pages/,
components/sections/, components/RouteLoader.tsx, lib/{cms-content,cms-site,seo-meta,query,store,head}.ts,
seo/{sitemap,robots,og}.gen.ts, plus public/images/<section>/ and .learnings/.)

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
});
```

## SSG entry (vite-react-ssg)

`src/main.tsx` exports the routes for `vite-react-ssg` and lists the locale × route params to
pre-render (the `getStaticPaths` equivalent). Each pre-rendered HTML carries localized content
+ head tags in the raw markup.

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

## Hard rules

- NEVER `create-next-app`, `app/` router, `next.config`, `middleware.ts`, `next/font`,
  `next/image`, `generateMetadata`. This is a Vite SPA.
- Locale lives in the URL segment (`/:locale/...`) via React Router; every page nests under it.
- Use `<img>` with `srcset`/`sizes` (or a small `<Image>` wrapper), not `next/image`.
```

- [ ] **Step 3: Delete the retired skill folder**

```bash
git rm -r ".claude/skills/nextjs-app-scaffolding"
```

- [ ] **Step 4: Verify no dangling references to the old skill name**

Run a repo-wide search for `nextjs-app-scaffolding`. Expected after this task: every hit is one
this plan will update in a later task (the agent skill table — Task 5; AGENTS.md — Task 6;
phase 3 — Task 7). There must be NO references that no task touches. List the hits to confirm.

- [ ] **Step 5: Stage**

```bash
git add ".claude/skills/vite-react-scaffolding/SKILL.md"
git add -A ".claude/skills/nextjs-app-scaffolding"
```

---

### Task 2: Rewrite `i18n-setup` (next-intl → react-i18next)

**Files:**
- Modify: `.claude/skills/i18n-setup/SKILL.md`

**Interfaces:**
- Consumes: the `src/i18n/` paths and `messages/<locale>.json` shape from Task 1.
- Produces: the `react-i18next` init contract that the connector (Plan B) and phases 3/9 rely on
  — namespaced `t("ns.key")`, `messages/<locale>.json` per locale, locale from URL segment.

- [ ] **Step 1: Read** `.claude/skills/i18n-setup/SKILL.md` fully; note every next-intl API it mandates (`defineRouting`, `createNavigation`, `createMiddleware`, `createNextIntlPlugin`, `NextIntlClientProvider`, `setRequestLocale`, `getMessages`, `getTranslations`, `generateStaticParams`, `app/sitemap.ts`).

- [ ] **Step 2: Rewrite** to the react-i18next model. Mandated replacements (each old → new must appear):
  - Install: `next-intl` → `react-i18next i18next i18next-browser-languagedetector`.
  - Routing: `i18n/routing.ts` (`defineRouting`) + `middleware.ts` → React Router `/:locale` parent route + a `<LocaleGuard>` that validates the segment and sets `i18n.changeLanguage(locale)`.
  - Provider: `NextIntlClientProvider` → `<I18nextProvider i18n={i18n}>` initialized in `src/i18n/config.ts` with `resources` built from `messages/<locale>.json`, `fallbackLng` = default locale, `supportedLngs`.
  - Translation call: keep `t("ns.key")` (react-i18next supports namespaces) — **the JSON shape does not change** (this is deliberate; the connector merges over it).
  - Static params: `generateStaticParams()` → the explicit `locales × routes` list passed to `vite-react-ssg` (Task 1's `main.tsx`).
  - hreflang/sitemap: moved to `seo-pro` (Task 3) — cross-reference it, don't duplicate.
  - Keep: the "non-default seed files mirror the default locale (no `[XX]` placeholders for a from-scratch build); the CMS auto-translates once connected" rule, restated for react-i18next.
  - Language switcher: navigate to the other locale prefix, call `i18n.changeLanguage`, persist via `useLocaleStore` (Task 1).

- [ ] **Step 3: Verify** the file no longer contains `next-intl`, `NextIntlClientProvider`, `createMiddleware`, `createNextIntlPlugin`, `getMessages`, `setRequestLocale`, or `app/[locale]`. Confirm `messages/<locale>.json` and `t(` still appear (shape preserved). Confirm a `react-i18next` import path is present.

- [ ] **Step 4: Stage** `git add ".claude/skills/i18n-setup/SKILL.md"`

---

### Task 3: Rewrite `seo-pro` (Next Metadata API → React 19 head hoisting + prebuild SSG)

**Files:**
- Modify: `.claude/skills/seo-pro/SKILL.md`

**Interfaces:**
- Consumes: `lib/head.ts`, `lib/seo-meta.ts`, `seo/{sitemap,robots,og}.gen.ts` from Task 1.
- Produces: the build-time SEO contract phases 5/9 + the connector (Plan B) rely on — head tags
  baked at pre-render, prebuild sitemap/robots/OG, build-time stored-meta fetch, coded tags
  generated locally per locale.

- [ ] **Step 1: Read** `.claude/skills/seo-pro/SKILL.md`; mark the stack-agnostic parts to keep verbatim (JSON-LD shapes, schema.org types, the audit checklist, the 1200×630 OG spec) vs the Next API parts to replace (`generateMetadata`, separate `viewport` export, `metadataBase`, `app/sitemap.ts` `MetadataRoute.Sitemap`, `app/robots.ts` `MetadataRoute.Robots`, `next/og` `ImageResponse`).

- [ ] **Step 2: Rewrite** the API layer. Mandated replacements:
  - **Per-page metadata:** `generateMetadata` + separate `viewport` export → a `lib/head.ts`
    `buildHead(route, locale)` returning the tag set, rendered as React 19 hoisted
    `<title>/<meta>/<link>` inside the page component (React lifts them to `<head>`; baked into
    the pre-rendered HTML by `vite-react-ssg`). Viewport is a plain `<meta name="viewport">`.
  - **metadataBase:** a `SITE_URL` constant in config (ask for the domain if unknown; never
    `example.com`).
  - **sitemap:** `app/sitemap.ts` → `src/seo/sitemap.gen.ts` (prebuild) writing
    `public/sitemap.xml` (every locale × page, with hreflang alternates).
  - **robots:** `app/robots.ts` → `src/seo/robots.gen.ts` → `public/robots.txt`.
  - **OG images:** `next/og` `ImageResponse` → `src/seo/og.gen.ts` using `satori` + `@resvg/resvg-js`/`sharp` → `public/og/*.png` (keep 1200×630). Note the Playwright-screenshot fallback if a font breaks satori.
  - **Stored SEO meta:** `lib/seo-meta.ts` fetches
    `GET {backend}/projects/{slug}/seo/public/meta?route=&locale=<locale>` at **build time**
    (no ISR), prefers stored prose, falls back to build-time output, **never throws**. The
    **coded tags** (`canonical`, `hreflang`, `og:locale`, JSON-LD `inLanguage`) are generated
    **locally per locale** in `lib/head.ts` — not fetched. Per-field default-locale fallback is
    applied by the **endpoint**, so the site never merges locales.
  - **Keep verbatim:** JSON-LD `<script type="application/ld+json">` per page type, schema.org
    types, the audit checklist.

- [ ] **Step 3: Verify** the file no longer mandates `generateMetadata`, `MetadataRoute`,
  `next/og`, or a separate `viewport` export, and now references `lib/head.ts`,
  `src/seo/sitemap.gen.ts`, `src/seo/robots.gen.ts`, `src/seo/og.gen.ts`, and build-time
  `seo/public/meta` fetch. Confirm JSON-LD + schema types survived.

- [ ] **Step 4: Stage** `git add ".claude/skills/seo-pro/SKILL.md"`

---

### Task 4: Light skill touch-ups (motion / responsive / playwright)

**Files:**
- Modify: `.claude/skills/motion-animations/SKILL.md`
- Modify: `.claude/skills/responsive-audit/SKILL.md`
- Modify: `.claude/skills/playwright-user-stories/SKILL.md`

- [ ] **Step 1: motion-animations** — change the descriptor "in a Next.js + React project" → "in a React 19 project". No other edits (import stays `motion/react`). Verify no `next/*` reference remains.

- [ ] **Step 2: responsive-audit** — replace the `next/image` `sizes` example with a plain
  `<img srcset sizes>` (or `<Image>` wrapper) example; keep all breakpoint/Tailwind/a11y content. Verify `next/image` no longer appears.

- [ ] **Step 3: playwright-user-stories** — update the dev-server note to Vite (`npm run dev` →
  Vite on its default port; keep the Windows `127.0.0.1` guidance), and the `/` → `/<default-locale>`
  redirect note to "client-side React Router redirect + pre-rendered redirect stub". Replace the
  `next-intl` mention with the react-i18next/URL-segment locale mechanism. Verify `next-intl` no
  longer appears.

- [ ] **Step 4: Stage** `git add ".claude/skills/motion-animations/SKILL.md" ".claude/skills/responsive-audit/SKILL.md" ".claude/skills/playwright-user-stories/SKILL.md"`

---

### Task 5: Rewrite the agent file `.claude/agents/website-builder.md`

**Files:**
- Modify: `.claude/agents/website-builder.md`

- [ ] **Step 1: Frontmatter `description`** — replace "multilingual Next.js 16 websites" with
  "multilingual Vite + React 19 SPAs (SSG-prerendered)". Keep `tools`, `model`, `effort`.

- [ ] **Step 2: Body stack references** — first-steps line, the one-line plan template, and the
  intro all change "Next.js 16 website" → "Vite + React 19 SPA (SSG)".

- [ ] **Step 3: Replace the Hard-constraints block** (currently the Next-specific bullet list)
  with this exact set:

```markdown
5. **Hard constraints — never violate:**
   - Animation library is **`motion`** (`import { motion } from "motion/react"`). NEVER `framer-motion`.
   - i18n is **`react-i18next`** (namespaced `t()`, `messages/<locale>.json`). NEVER `next-intl`/`next-i18next`/`react-intl`.
   - Build tool is **Vite 7 + React 19**, pre-rendered by **`vite-react-ssg`**. NEVER Next.js, `app/` router, `next.config`, `middleware.ts`.
   - Routing is **React Router v7 (library mode)**, locale-prefixed `/:locale/...`. Every page nests under the locale segment, even single-locale sites.
   - Head/SEO via **React 19 hoisted `<title>/<meta>/<link>`** + `lib/head.ts`; sitemap/robots/OG are **prebuild scripts** → `public/`. NEVER `generateMetadata`, `app/sitemap.ts`, `next/og`.
   - Fonts via `@fontsource*` + CSS `@import`. NEVER `next/font`. Images via `<img srcset>`/an `<Image>` wrapper. NEVER `next/image`.
   - **localStorage is first-class:** data cache = TanStack Query persisted to localStorage (`lib/query.ts`); app/UI state = Zustand `persist` (`lib/store.ts`). (This REPLACES the old "never use localStorage" rule.)
   - All clickable elements have accessible names; all images have `alt`; all forms have labels. Mobile-first; verify 375/768/1024/1440 before done.
   - Ship the **browser-translation resilience shim** as the first inline `<script>` in `index.html` (patch `Node.prototype.removeChild`/`insertBefore` when `child.parentNode !== this`; never patch `replaceChild`). Add `suppressHydrationWarning` on `<html>` (covers translator mutation; relevant on the SSG-hydrated path).
   - Booking/selection UI: the week-paginated 7-day picker, per-card cross-fade select, responsive icon-only pill, and no-scroll success screen behave exactly as before (framework-agnostic component patterns).
   - Inter-page route loader is first-class: a themed full-screen splash as the React Router Suspense `fallback` (`components/RouteLoader.tsx`) with a dedicated localized `loader.routeLoading` key; z-index above header + mobile menu; respect reduced-motion.
```

- [ ] **Step 4: Skills table** — rename the `nextjs-app-scaffolding` row to `vite-react-scaffolding`; keep the rest (the phase mapping is unchanged).

- [ ] **Step 5: "What you must NEVER do" list** — replace `framer-motion`/`next-i18next`/`pages/`/`<img> outside next/og`/`app/[locale]` items with: never use Next.js / `app/` router / `next.config`; never `framer-motion`; never `next-intl`; never `generateMetadata`/`next/og`/`next/image`/`next/font`; never skip the locale URL segment; never nest output inside "CMS - websites". Keep the non-stack items (auto-translate, replace mock images, skip clarifying questions, mark unimplemented BUILD_PLAN items done, delete `.learnings/`, loop forever).

- [ ] **Step 6: Verify** the file contains no `next-intl`, `app/[locale]`, `generateMetadata`,
  `next/font`, `next/image`, or `framer-motion`, and the skills table row reads
  `vite-react-scaffolding`. Confirm the localStorage line now says "first-class".

- [ ] **Step 7: Stage** `git add ".claude/agents/website-builder.md"`

---

### Task 6: Rewrite `agents/Website Builder/AGENTS.md`

**Files:**
- Modify: `agents/Website Builder/AGENTS.md`

- [ ] **Step 1: "What it does"** — "production-grade, multilingual Next.js 16 site" → "Vite +
  React 19 SPA with build-time SSG pre-rendering".

- [ ] **Step 2: Constants table** — update rows: Component library stays shadcn/ui; Animation stays Motion; **i18n library → react-i18next**; **add rows**: Build tool = Vite 7 + React 19; SSG = vite-react-ssg; Router = React Router v7 (library); Data cache = TanStack Query (localStorage-persisted); App state = Zustand (persist); **Hosting target → static `dist/` (Vercel static or nginx Docker); remove `output: 'standalone'`**.

- [ ] **Step 3: The 8 phases** — rewrite phase 3 (scaffold `vite-react-scaffolding` + `i18n-setup`,
  Vite app, react-i18next, copy mock images, copy learnings-template) and phase 5 (SEO via build-time
  head + prebuild sitemap/robots/OG + build-time stored-meta fetch; "**pre-render** every locale,
  raw-HTML per locale"). Phases 1,2,4,6,7,8 keep their wording except any `generateMetadata`/`app/`
  references in phase 5's prose.

- [ ] **Step 4: Incremental-mode section** — "adds new `app/[locale]/<route>/page.tsx`" → "adds a
  route-table entry in `routes.tsx` + `pages/<name>.tsx` + the locale×route pre-render entry"; the
  SEO-area-aware paragraph changes `generateMetadata` request-time/ISR/active-locale-server-fallback
  → build-time head + client refetch; "SSR every locale" → "pre-render every locale"; keep
  additive-only + `cms-preview`-only + same-bar.

- [ ] **Step 5: Gotchas** — DELETE the "Next 16 root layout" gotcha; REPLACE with an "SPA mount +
  translation shim in `index.html`" gotcha. Keep (reworded for Vite where needed):
  env/CORS/dev-origin (now `VITE_*` vars, open Vite dev at the printed origin), week-picker,
  cross-fade, responsive pill, no-scroll success, route loader (now a Suspense fallback).

- [ ] **Step 6: Verify** AGENTS.md has no `Next.js`, `app/[locale]`, `generateMetadata`,
  `output: 'standalone'`, `next-intl` (except where explicitly naming what NOT to use). Confirm the
  Constants table lists Vite/vite-react-ssg/React Router/TanStack/Zustand.

- [ ] **Step 7: Stage** `git add "agents/Website Builder/AGENTS.md"`

---

### Task 7: Rewrite `phases/3-scaffold.md`

**Files:**
- Modify: `agents/Website Builder/phases/3-scaffold.md`

- [ ] **Step 1: Replace the "Do" list** with the Vite flow:
  - `cd` to the parent scratch dir, then `npm create vite@latest <folder> -- --template react-ts`.
  - Install deps per `vite-react-scaffolding` (react-router-dom, react-i18next + i18next, @tanstack/react-query (+ persist + sync-storage-persister), zustand, motion, lucide-react; dev: vite-react-ssg, satori, @resvg/resvg-js, sharp, @playwright/test, @axe-core/cli, tailwindcss + @tailwindcss/vite).
  - Wire react-i18next: `src/i18n/config.ts`, `messages/<locale>.json` seed files mirroring the default locale; locale via React Router `/:locale` + `<LocaleGuard>`. Once CMS-connected (`VITE_CMS_ENDPOINT` set), content loads live per locale and the CMS auto-translates. See `i18n-setup`.
  - Set up `lib/query.ts` (QueryClient + localStorage persister) and `lib/store.ts` (Zustand persist stores).
  - Fonts via `@fontsource*` + `src/index.css` `@import`. Tailwind v4 via `@tailwindcss/vite`.
  - Add the translation-resilience shim as the first inline `<script>` in `index.html`.
  - Create the canonical `src/` folder structure from `vite-react-scaffolding`.

- [ ] **Step 2: Verify** the phase no longer references `create-next-app`, `next-intl`,
  `next.config.ts`, `middleware.ts`, `next/font`, or `app/[locale]`, and now references
  `npm create vite`, `vite-react-ssg`, react-i18next, `lib/query.ts`, `lib/store.ts`, `VITE_CMS_ENDPOINT`.

- [ ] **Step 3: Stage** `git add "agents/Website Builder/phases/3-scaffold.md"`

---

### Task 8: Rewrite `phases/5-seo.md`

**Files:**
- Modify: `agents/Website Builder/phases/5-seo.md`

- [ ] **Step 1: Replace the "Do" list** with the SSG SEO flow:
  - Per-page head via `lib/head.ts` rendered as React 19 hoisted tags (locale-specific
    title/description); plain `<meta name="viewport">`.
  - hreflang `<link>` for every locale on every page (generated locally per locale).
  - `src/seo/sitemap.gen.ts` → `public/sitemap.xml` (every locale × page, hreflang alternates);
    `src/seo/robots.gen.ts` → `public/robots.txt` (prebuild scripts).
  - JSON-LD per page type (Organization/LocalBusiness on home; appropriate type elsewhere),
    honoring the locale's name/description.
  - `src/seo/og.gen.ts` → `public/og/*.png` (satori + sharp; per-locale variants if locales
    differ significantly).
  - Set real `SITE_URL` (ask for the domain if unknown; never `example.com`).
  - Stored-meta: `lib/seo-meta.ts` fetches `seo/public/meta` at build time, prefers stored prose,
    falls back to build-time output, never throws; coded tags generated locally per locale;
    pre-render every locale (raw-HTML content per locale).

- [ ] **Step 2: Verify** the phase no longer references `generateMetadata`, `app/sitemap.ts`,
  `app/robots.ts`, `app/opengraph-image.tsx`, `metadataBase`, or a separate `viewport` export, and
  now references `lib/head.ts`, `src/seo/*.gen.ts`, satori, build-time `seo/public/meta`.

- [ ] **Step 3: Stage** `git add "agents/Website Builder/phases/5-seo.md"`

---

### Task 9: Rewrite `phases/9-incremental.md`

**Files:**
- Modify: `agents/Website Builder/phases/9-incremental.md`

- [ ] **Step 1: Replace the route-add mechanics:**
  - "add `app/[locale]/<route>/page.tsx`" → "add a route entry to `src/routes.tsx`
    (lazy-loaded), create `src/pages/<name>.tsx`, and add the `<route> × locales` entry to the
    `vite-react-ssg` pre-render list in `src/main.tsx`" — additive only, never restructure an
    existing route.
  - SEO: `generateMetadata` prefers stored meta → `lib/head.ts` + `lib/seo-meta.ts` build-time
    fetch (prefers stored prose, falls back, never throws); coded tags local per locale;
    **pre-render** every locale (raw-HTML per locale).
  - `consumes: seo_articles` → `/blog` index + `/blog/:slug` routes whose pre-render list is
    generated from the article slugs fetched at build time (`seo/public/articles`); client
    refetch keeps it fresh for humans.
  - Nav + i18n: add the `nav.label_i18n` key (and every new string) to every
    `messages/<locale>.json` (shape unchanged).
  - Push additive routes to `cms-preview`; hand back to the SEO agent's visual-QA gate (now a
    `pre-render` content-in-raw-HTML check). A publish triggers the rebuild hook (Plan B).

- [ ] **Step 2: Verify** the phase no longer references `app/[locale]`, `generateMetadata`, ISR
  (`revalidate`), or "active-locale server-side", and now references `routes.tsx`, `pages/`,
  `main.tsx` pre-render list, `lib/head.ts`, build-time articles fetch.

- [ ] **Step 3: Stage** `git add "agents/Website Builder/phases/9-incremental.md"`

---

### Task 10: Update `learnings-template/conventions.md` + append `LEARNINGS.md` entry

**Files:**
- Modify: `agents/Website Builder/learnings-template/conventions.md`
- Modify: `agents/Website Builder/LEARNINGS.md`

- [ ] **Step 1: conventions.md** — replace the App-Router conventions:
  - "Every page lives under `app/[locale]/`" → "Every page is a React Router route under the
    `/:locale` segment (`routes.tsx` + `pages/`)".
  - The `viewport` export note → "viewport is a plain `<meta>`; head tags are React 19 hoisted".
  - The "root layout in `app/[locale]/layout.tsx`" section → "the app shell is
    `src/App.tsx`/route layout; `index.html` holds `<html>`/`<body>` + the translation shim".
  - The `loading.tsx` note → "the route loader is a React Router Suspense `fallback`
    (`components/RouteLoader.tsx`)".
  - Add a convention: "data caching = TanStack Query persisted to localStorage; app state =
    Zustand `persist`".

- [ ] **Step 2: LEARNINGS.md** — append a dated entry:

```markdown
## 2026-06-20 — Builder now emits Vite + React 19 (SSG), not Next.js

**Lesson:** From-scratch builds are Vite 7 + React 19 SPAs pre-rendered by vite-react-ssg
(React Router v7 library mode, react-i18next, TanStack Query + Zustand persisted to
localStorage). SEO moves from `generateMetadata`/ISR to build-time head hoisting + prebuild
sitemap/robots/OG + a build-snapshot-plus-client-refetch freshness model. The old "never use
localStorage" rule is SUPERSEDED — localStorage is now first-class. The Next-root-layout lesson
below is obsolete for new builds.

**Apply:** Scaffold via `vite-react-scaffolding`; never `create-next-app`/`app/`/`next-intl`/
`generateMetadata`.
```

- [ ] **Step 3: Verify** conventions.md has no `app/[locale]`, `loading.tsx`, or `viewport export`
  mandate, and LEARNINGS.md has the new entry.

- [ ] **Step 4: Stage** `git add "agents/Website Builder/learnings-template/conventions.md" "agents/Website Builder/LEARNINGS.md"`

---

### Task 11: Integration dry-run — build one real site on the new stack

This is the executable verification for the whole plan. It needs a design input; if none is
handy, use the simplest available design export under a sibling scratch folder, or ask Stefan
for one.

**Files:** none modified (produces a throwaway site in a sibling scratch folder).

- [ ] **Step 1:** Invoke the rewritten website-builder agent on a small design export (one
  business, EN + NL). Let it run phases 1–8.

- [ ] **Step 2: Verify scaffold** — the output folder has `vite.config.ts` (no `next.config`),
  `src/routes.tsx`, `src/i18n/config.ts`, `src/lib/query.ts`, `src/lib/store.ts`, and an
  `index.html` whose first `<script>` is the translation shim.

- [ ] **Step 3: Verify build** — in the output folder, `npm run build` exits 0 (vite-react-ssg
  pre-render succeeds).

Run: `cd "<output>" && npm run build`
Expected: exit 0; `dist/` contains per-locale HTML.

- [ ] **Step 4: Verify SSG content-in-raw-HTML** — grep a pre-rendered `dist/en/index.html` and
  `dist/nl/index.html` for visible localized hero copy and a `<title>` + hreflang `<link>`.
  Expected: localized content present in raw HTML for BOTH locales (the SEO guarantee).

- [ ] **Step 5: Verify localStorage wiring** — grep the built/source for
  `createSyncStoragePersister` (query cache) and `persist(` (Zustand). Expected: both present.

- [ ] **Step 6: Verify smoke tests** — `npm run test:e2e` passes the per-locale smoke specs (or
  the agent's Phase 7 reports green). Fix the SITE, not the test.

- [ ] **Step 7: Report** the dry-run result (folder path, build status, raw-HTML check, test
  result). Do NOT commit the throwaway site. Stage nothing here.

---

## Self-Review

**Spec coverage:**
- New stack (Vite/React/vite-react-ssg/React Router/react-i18next/TanStack/Zustand) → Tasks 1–3, 5–10; verified end-to-end in Task 11. ✓
- Freshness Option B (build snapshot + client refetch; rebuild-on-publish) → build snapshot + client refetch land in Tasks 1/3/8/9; the **rebuild-on-publish hook is a Plan B (downstream) item** — noted in Tasks 9 and the spec. ✓ (Plan A intentionally stops at the builder's side of the contract.)
- localStorage flip → Tasks 1 (query/store), 5 (hard-constraint inversion), 10 (convention). ✓
- SEO without Next (head hoisting, prebuild sitemap/robots/OG, build-time stored-meta) → Tasks 3, 8. ✓
- i18n preserving `t()`/`messages` shape → Tasks 2, 7. ✓
- Carried-over gotchas (translation shim, booking UI, route loader) → Tasks 1, 5, 6. ✓
- Skill rename + reference updates → Task 1 (create/delete) + Tasks 5/6/7 (references). ✓
- Downstream connector + SEO agent → **explicitly out of scope for Plan A; Plan B.** ✓

**Placeholder scan:** Doc tasks show the exact mandated replacements and verification greps; the
anchor skill (Task 1) and the hard-constraints block (Task 5) are shown in full. No "TBD"/"add
appropriate X". ✓

**Type/name consistency:** Skill name `vite-react-scaffolding` (Tasks 1,5,6,7); file paths
`lib/{query,store,head,seo-meta,cms-content,cms-site}.ts`, `seo/{sitemap,robots,og}.gen.ts`,
`routes.tsx`, `pages/`, `main.tsx`, `components/RouteLoader.tsx`, `messages/<locale>.json`,
`VITE_CMS_ENDPOINT` — used identically across tasks. ✓

## Plan B preview (separate file, authored next)

Downstream alignment: `agents/SEO-GEO Optimizer/{site_change_spec.py, phases/7-learn.md}` and
`agents/CMS Connector - Website/{scan.py, prompts.py, phases/4-integration.md, AGENTS.md,
LEARNINGS.md}` — move the contract from request-time-ISR/`generateMetadata`/active-locale-server-
fallback to build-time-snapshot + client-refetch + **rebuild-on-publish deploy hook**; default
env prefix `NEXT_PUBLIC_` → `VITE_`; keep "never provision/clobber `seo_*`" and legacy-Next
detection for already-imported sites.
