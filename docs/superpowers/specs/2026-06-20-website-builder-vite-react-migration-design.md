# Website Builder → Vite + React 19 (SSG) Migration — Design

**Date:** 2026-06-20
**Status:** Approved design, pending implementation plan
**Author:** website-builder maintainer (Stefan + Claude)

## Goal

Convert the **website-builder** agent from producing **Next.js 16** sites to producing
**Vite + React 19 single-page apps with build-time SSG pre-rendering**. Make builds and dev
fast (Vite HMR + persistent cache), make navigation smooth (route-level code-splitting,
Motion), implement runtime **caching** (TanStack Query persisted to localStorage), and store
client state in **localStorage** (Zustand `persist`). The current agent *forbids* localStorage
because Next SSR breaks on it; a client SPA removes that constraint, so localStorage becomes
first-class.

This is a **full replacement** — the agent no longer emits Next.js sites — and the change
**reaches downstream**: the SEO/GEO Optimizer's incremental "add pages" mode and the CMS
connector are updated so the whole pipeline is React/Vite-aware.

## Locked decisions

| Decision | Choice |
|---|---|
| Build tool | **Vite 7** + **React 19** |
| SSG / pre-render | **vite-react-ssg** (per route × locale → static HTML; SEO in raw HTML) |
| Routing | **React Router v7, library mode** (not framework mode → stays "just React"), locale-prefixed `/:locale/...` |
| i18n | **react-i18next** (keeps `t()` + namespaced `messages/<locale>.json` → minimal connector churn) |
| Head / metadata | **React 19 native `<title>`/`<meta>`/`<link>` hoisting** + a build-time head injector; sitemap/robots via prebuild script; OG images pre-generated (satori + sharp) |
| Data cache | **TanStack Query** + `@tanstack/react-query-persist-client` → localStorage |
| App/UI state | **Zustand** + `persist` middleware → localStorage |
| Content freshness | **Option B** — SSG build-time snapshot (crawler SEO) + client refetch (fresh for humans) + rebuild-on-publish hook |
| Stack replaced | Next.js entirely; no Next path retained |
| Carried over unchanged | Motion (`motion/react`), shadcn/ui, Tailwind v4, Playwright, translation-resilience shim, booking week-picker / cross-fade / no-scroll success, themed route loader |
| Hosting | Static `dist/` → Vercel static (or nginx Docker). No Node server required. |
| Output folder | unchanged — sibling `scratch\<business-name>\` |

## The freshness model (Option B) — the architectural crux

Next's model is **request-time** fetch + ISR (CMS publish appears within ~60s, no rebuild). A
static SSG site bakes content at build time. We resolve the gap with a two-layer model:

1. **Build-time layer (SEO / crawlers).** `vite-react-ssg` pre-renders every route × locale.
   The prebuild fetches the latest **published** CMS content and stored `seo_page_meta` and
   bakes them into the raw HTML (`<title>`, `<meta>`, hreflang `<link>`, JSON-LD `<script>`,
   visible copy). This is the snapshot AI/Google bots see — content is in raw HTML per locale,
   exactly as the SEO contract requires.

2. **Client layer (humans / freshness).** After hydration, **TanStack Query** refetches live
   **published** content + SEO prose from the CMS, updates the view, and persists the response
   to **localStorage** (instant warm loads, stale-while-revalidate). Human visitors therefore
   see fresh content immediately with no rebuild.

3. **Rebuild-on-publish.** To refresh the crawler snapshot, a CMS/SEO **publish** triggers a
   Vercel deploy hook (the pipeline already has prod deploy hooks). The crawler snapshot can lag
   between rebuilds; acceptable for marketing copy.

Consequence: the old per-field, **server-side** default-locale fallback (the endpoint filling
missing translated fields) moves to **build time** for the snapshot and is applied by the
**public endpoint** for the client refetch — the site still **never merges locales itself**.
Coded tags (`canonical`, `hreflang`, `og:locale`, JSON-LD `inLanguage`) are generated **locally
per locale** at build (language-invariant codes, not fetched), unchanged in spirit.

## New site architecture (what a generated site looks like)

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

### Routing
React Router v7 library mode. A single route table with a `/:locale` parent segment; every page
nests under it. `generateStaticParams` → an explicit `locales × routes` list fed to
`vite-react-ssg` so each combination pre-renders. `/` → redirect to the geo/default locale
(client redirect + a pre-rendered redirect stub for crawlers).

### i18n
`react-i18next` initialized from `messages/<locale>.json`. Same `t("ns.key")` call sites and
same namespaced JSON shape the connector already targets — so the connector's
`cms-content.ts` merge and `resolveSite()` survive. Locale comes from the URL segment (not
middleware). Language switch = navigate to the other locale prefix + `i18n.changeLanguage` +
persist choice in the Zustand `locale` store.

### SEO without Next
- **Per-page head:** React 19 lets us render `<title>/<meta>/<link>` inside components; React
  hoists them to `<head>`. `lib/head.ts` builds the tag set per route × locale; baked into the
  pre-rendered HTML by `vite-react-ssg`. Replaces `generateMetadata` + separate `viewport`
  export.
- **sitemap.xml / robots.txt:** generated by prebuild scripts into `public/` (replaces
  `app/sitemap.ts` / `app/robots.ts`).
- **JSON-LD:** unchanged concept — a `<script type="application/ld+json">` rendered per page,
  baked at build.
- **OG images:** pre-generated PNGs via satori + sharp at build (replaces `next/og`
  `ImageResponse`).
- **Stored SEO meta:** `lib/seo-meta.ts` fetches `GET /projects/{slug}/seo/public/meta` at
  **build time** for the snapshot and (optionally) on the client; prefers stored prose, falls
  back to build-time `seo-pro` output, never throws. Coded tags generated locally per locale.

### State + caching (the explicit ask)
- **TanStack Query** is the data layer: CMS content, SEO prose, booking availability. Persisted
  to localStorage via `persistQueryClient` + `createSyncStoragePersister` → instant warm loads,
  background revalidation.
- **Zustand `persist`** holds UI/app state in localStorage: active locale, booking flow
  selections (service / staff / date / week offset), mobile-menu open, theme. Survives reloads.
- **Vite** gives fast compile: dependency pre-bundling + persistent `node_modules/.vite` cache;
  `manualChunks` for vendor splitting; route-level `React.lazy` for smooth nav.

### Carried-over gotchas (framework-agnostic, kept)
- **Translation-resilience shim:** the `Node.prototype.removeChild`/`insertBefore` patch moves
  to an inline `<script>` at the top of `index.html` (runs before React mounts). Do NOT patch
  `replaceChild`. `suppressHydrationWarning` guidance applies only on the SSG-hydrated path.
- **Booking UI:** week-paginated 7-day picker (`grid repeat(7,1fr)`, lazy per-week availability,
  reset on service/staff change, directional `AnimatePresence` slide), per-card cross-fade
  select, responsive icon-only pill, no-scroll success screen — all kept verbatim.
- **Route loader:** the themed full-screen splash with `loader.routeLoading` becomes a React
  Router Suspense `fallback` (`RouteLoader.tsx`), same visual + reduced-motion behavior.

## Per-file change inventory

### Workstream A — Builder core + skills (self-contained)

| File | Change |
|---|---|
| `.claude/agents/website-builder.md` | Rewrite stack references (Next→Vite/React); flip the localStorage prohibition to first-class; update hard-constraints (routing, fonts via CSS/`@fontsource` not `next/font`, no `next/image`), skills table, NEVER-list |
| `agents/Website Builder/AGENTS.md` | Rewrite "what it does", Constants table, the 8 phases (esp. 3 & 5), incremental-mode section, gotchas (root-layout item removed, replaced by SPA-mount + shim), hosting target |
| `agents/Website Builder/phases/3-scaffold.md` | `create-next-app` → `npm create vite` + vite-react-ssg + react-router + react-i18next + TanStack Query + Zustand wiring; canonical Vite folder structure |
| `agents/Website Builder/phases/5-seo.md` | `generateMetadata`/`sitemap.ts`/`robots.ts`/`next/og` → React 19 head hoisting + prebuild sitemap/robots/OG; build-time stored-meta fetch |
| `agents/Website Builder/phases/9-incremental.md` | `app/[locale]/<route>/page.tsx` → add route-table entry + `pages/<name>.tsx` + pre-render list entry; build-time meta; rebuild-on-publish |
| `agents/Website Builder/learnings-template/conventions.md` | Replace App-Router conventions (`app/[locale]/`, `viewport` export, `loading.tsx`, root-layout rule) with Vite/React-Router equivalents |
| `agents/Website Builder/LEARNINGS.md` | Append a migration entry; the Next-root-layout lesson is marked superseded |
| `.claude/skills/nextjs-app-scaffolding/` | **Rename → `vite-react-scaffolding`**; full rewrite to Vite scaffold; update all references (agent skill table, phase 3, AGENTS.md, SessionStart registry) |
| `.claude/skills/i18n-setup/SKILL.md` | next-intl → react-i18next + React Router locale segments + build-time `generateStaticParams`-equivalent; keep `messages/<locale>.json` shape |
| `.claude/skills/seo-pro/SKILL.md` | Replace Next API layer (metadata/sitemap/robots/og) with Vite/SSG equivalents; keep JSON-LD, schema types, audit checklist, OG spec |
| `.claude/skills/motion-animations/SKILL.md` | One-line descriptor (`Next.js + React` → `React 19`) |
| `.claude/skills/responsive-audit/SKILL.md` | `next/image sizes` note → `<img>`/srcset equivalent |
| `.claude/skills/playwright-user-stories/SKILL.md` | `baseURL`/locale-redirect notes → Vite dev server + SPA redirect |
| `.claude/skills/design-handoff/SKILL.md` | No change (stack-agnostic) |

### Workstream B — Downstream pipeline (depends on A's contract)

| File | Change |
|---|---|
| `agents/SEO-GEO Optimizer/site_change_spec.py` | Drop `app/[locale]` routing assumptions from the contract comments/validation; route field stays framework-neutral; add `rebuild_on_publish` note |
| `agents/SEO-GEO Optimizer/phases/7-learn.md` | "add routes to Next app" → "add route-table entries via Builder incremental"; publish step triggers rebuild hook |
| `agents/CMS Connector - Website/scan.py` | `_env_prefix` default `NEXT_PUBLIC_` → `VITE_` (Vite is now the only target); keep other-framework branches for legacy imports |
| `agents/CMS Connector - Website/phases/4-integration.md` | Env prefix → `VITE_`; runtime-ISR fetch (`next:{revalidate}`, `cache:"no-store"`) → build-time prebuild fetch + client TanStack refetch; `lib/cms-content.ts`/`lib/seo-meta.ts` Vite variants; blog `[slug]` → pre-generated route list; `generateMetadata` → build-time head + client refetch |
| `agents/CMS Connector - Website/AGENTS.md` | Rewrite multilingual-fetch + SEO-area contracts from request-time-ISR/`generateMetadata`/active-locale-server-fallback to build-time-snapshot + client-refetch + rebuild-on-publish (keep "never provision/clobber `seo_*`") |
| `agents/CMS Connector - Website/LEARNINGS.md` | Append a migration entry noting the Next-era lessons (ISR, `output:"export"`, `NEXT_PUBLIC_`) are superseded for new builds; legacy imported Next sites still detected via `next.config` |

### Cross-agent contract delta (summary)
- `site-change-spec` stays the interface; only its routing assumption changes (`app/[locale]`
  file → route-table entry). Builder incremental remains additive-only, `cms-preview`-only,
  meets the same per-page bar.
- "SSR every locale (raw-HTML per locale)" → "**pre-render** every locale (raw-HTML per
  locale)". Same observable guarantee for the `seo-visual-qa` `content-in-raw-HTML` check.
- Publish (CMS or SEO agent) now additionally **triggers a rebuild deploy hook** so the crawler
  snapshot reflects the latest content.

## Non-goals / out of scope
- Migrating already-deployed client sites (samir-kapsalon, Laurian, it-global-services) off
  Next. They stay Next; the connector keeps detecting/serving legacy Next imports. Only
  **new from-scratch builds** use the Vite stack.
- A Node SSR server / true ISR. We use static SSG + client refetch, not a running server.
- Changing the CMS backend, Supabase schema, or the `seo_*` tables. The public read endpoints
  are consumed as-is (build-time + client), not modified.

## Risks & mitigations
- **Crawler snapshot lag.** Mitigated by rebuild-on-publish hook; acceptable for marketing copy.
- **Connector content-merge regressions.** Mitigated by keeping `react-i18next`'s `t()` +
  `messages/<locale>.json` shape identical to next-intl's, so `cms-content.ts`/`resolveSite()`
  logic ports with minimal change.
- **Shared-skill blast radius (`seo-pro`, `i18n-setup`).** Only the website-builder produces new
  sites; SEO/GEO + connector reference these skills as concepts/floors. Workstream B updates the
  consuming docs in the same change set.
- **OG image generation parity.** satori+sharp ≠ `next/og` exactly; mitigated by keeping the
  1200×630 spec and a Playwright-screenshot fallback if satori struggles with a font.

## Implementation decomposition
- **Plan A** — Builder core + skills (Workstream A). Self-contained; defines the new contract.
- **Plan B** — Downstream connector + SEO agent (Workstream B). Depends on A.

Each plan gets its own `writing-plans` pass. This spec covers both so the contract is consistent
across them.

## Verification approach
These are agent **instruction** files (Markdown) plus small Python edits (`site_change_spec.py`,
`scan.py`). Verification is: (1) internal cross-reference consistency (no remaining Next-only
mandates in builder-produced output paths; skill-table/registry names resolve); (2) a real
end-to-end dry run — invoke the rewritten website-builder on one design export and confirm it
scaffolds a Vite+React+SSG site that builds (`vite build` exit 0), pre-renders per locale (grep
raw HTML for localized content), and passes its Playwright smoke; (3) Python edits keep
`site_change_spec.py` / `scan.py` test-green.
```
