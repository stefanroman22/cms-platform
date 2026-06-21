# Phase 9 — Incremental (add pages/sections)

> **This is a SEPARATE mode, not part of the from-scratch 8-phase build.** It is invoked by
> the **SEO/GEO Optimizer** agent through the **`site-change-spec`** contract — never as part
> of an initial build. When you receive a validated `site-change-spec`, run THIS phase only.

**Goal:** Given a validated `site-change-spec` (emitted + validated by the SEO/GEO Optimizer
via `agents/SEO-GEO Optimizer/site_change_spec.py`), **ADD** the specified routes/sections to
an **EXISTING** generated site — **additive only**, no full rebuild, never break an existing
route. Build each new page to the same bar as a from-scratch page (full `seo-pro` metadata,
responsive, Motion, real section components, per-locale), wire it to the SEO area, push to
`cms-preview`, then **hand back to the SEO agent's Phase-6 visual-QA gate** for verification
before any publish.

**Inputs:** the validated `site-change-spec` JSON —
`project_slug`, `repo`, `branch` (always `cms-preview`), `run_id`, `pages[]`
(`route`, `page_type`, `consumes`, `nav`, `schema_type`, `locales`), `sections[]`
(`target_route`, `component`, `schema_type`), `cms_wiring[]`
(`consumes`, `via` — e.g. `GET /projects/{slug}/seo/public/meta`), and `reason`. The repo's
existing `src/routes.tsx`, `src/pages/`, `src/main.tsx` pre-render list,
`i18n/messages/<locale>.json`, design tokens, and section component conventions.

## Steps

1. **Read the spec + the existing site.** Parse the `site-change-spec`. Inspect the existing
   `src/routes.tsx` route table, `src/pages/` components, the `src/main.tsx` pre-render list,
   the `i18n/messages/<locale>.json` files, the design tokens, and the existing section
   components — the new pages must MATCH the site's established aesthetic, layout primitives,
   and i18n conventions. Confirm `branch == "cms-preview"`.

2. **For each `page`, add a route entry + page component + pre-render entries** (additive —
   never overwrite an existing route):
   - **Route table:** add a lazy-loaded entry to `src/routes.tsx`:
     ```tsx
     { path: "/:locale/<route>", element: <Suspense fallback={<RouteLoader />}>{lazy(() => import("./pages/<Name>Page"))}</Suspense> }
     ```
     Additive only — never restructure or reorder existing route entries.
   - **Page component:** create `src/pages/<Name>Page.tsx`.
   - **Pre-render list:** add the `<route> × locales` entry to the `vite-react-ssg` pre-render
     list in `src/main.tsx` so every locale is pre-rendered (raw-HTML content per locale —
     AI/Google bots don't run JS). **Pre-render every locale.**
   - Full **`seo-pro`** metadata via `lib/head.ts` + `lib/seo-meta.ts`: call `buildHead(route,
     locale)` inside the page component and render the returned tag set as React 19 hoisted
     `<title>/<meta>/<link>` tags (baked into pre-rendered HTML by `vite-react-ssg`). No
     `generateMetadata`. `lib/seo-meta.ts` fetches
     `GET /projects/{slug}/seo/public/meta?route=<route>&locale=<locale>` at **build time**
     (no ISR, no request-time fetch) and **prefers stored prose** (title/description/OG text +
     JSON-LD data), falling back to the build-time `seo-pro` output on any error — **never
     throw**. The **per-field default-locale fallback is server-side** — the endpoint fills any
     missing/untranslated locale field from the default-locale row, so the page fetches one
     locale response and **never merges locales itself**. The **coded tags are generated LOCALLY
     per locale** — `canonical`, `hreflang` (`<link rel="alternate">`), `og:locale`, and
     JSON-LD `inLanguage` are language-invariant codes computed in `lib/head.ts`, NOT fetched.
   - Responsive at 375/768/1024/1440 + Motion (`motion/react`) + real section components built
     from the design tokens (not placeholders).
   - JSON-LD of `schema_type` (via `JsonLd` component from `lib/seo/jsonld.tsx`), honoring the
     locale's name/description.
   - **`consumes: "seo_articles"`** → add `/blog` index + `/blog/:slug` routes. The pre-render
     list for `/blog/:slug` is generated from the **article slugs fetched at build time** from
     `GET /projects/{slug}/seo/public/articles` (iterate every returned slug per locale and add
     a pre-render entry). The page component also refetches articles client-side (TanStack Query)
     so humans see the freshest list without a rebuild. An untranslated article transparently
     shows default-locale prose (server-side per-field fallback) — the page does not merge.
   - **`consumes: "seo_page_meta"`** → `lib/seo-meta.ts` reads `/seo/public/meta` at build time
     as above.
   - **`consumes: "static"` / `None`** → no remote fetch; render from the design content.

3. **For each `section`,** add the `component` to `target_route`'s page additively (append a
   section; do not restructure the existing page), with its `schema_type` JSON-LD where given.

4. **Nav + i18n.** For each page with `nav.add: true`, add the nav entry using `nav.label_i18n`
   as the message key, and add that key (+ every other new string) to **every** locale's
   `i18n/messages/<locale>.json`. Shape unchanged — no hard-coded strings; all copy flows through
   react-i18next `t()`.

5. **Per-locale Playwright smoke.** Run the existing `playwright-user-stories` smoke plus a
   smoke for each NEW route × locale (renders, no console error, links resolve). Fix the SITE,
   not the test. The from-scratch phases 5–7 bar applies to the new pages.

6. **Push to `cms-preview`.** Commit the additive changes and push to the `cms-preview` branch
   (the spec's `branch`). Do **NOT** push to the production branch and do **NOT** publish — the
   SEO/GEO Optimizer promotes to production only after its gate is green.

7. **Hand back to the SEO agent's Phase-6 gate.** Return control to the SEO/GEO Optimizer,
   which runs the **`seo-visual-qa`** gate (375/768/1440 per locale, responsive / visibility /
   no-crash / no-console-error / build-ok / links-resolve / **content-in-raw-HTML** — a
   pre-render content-in-raw-HTML check, passing because every locale is pre-rendered) over the
   new routes and publishes only when all-green (else halt + revert). This Builder mode never
   publishes by itself. A publish triggers the rebuild hook (Plan B / downstream — not
   implemented here).

## Outputs

- New additive route entries in `src/routes.tsx` + `src/pages/<Name>Page.tsx` components +
  locale × route entries in the `src/main.tsx` pre-render list (+ any `sections`) on the
  `cms-preview` branch, each with full `seo-pro` metadata via `lib/head.ts` + `lib/seo-meta.ts`
  build-time fetch (prefers stored prose, never throws), the `seo_articles` build-time slug
  fetch + client refetch where specified, nav entries + per-locale i18n keys in every
  `messages/<locale>.json`, and a green per-locale Playwright smoke. No existing route changed.
  Nothing published — handed back to the SEO agent's Phase-6 gate.

## Hard rules (incremental mode)

- **Additive only.** Never break or restructure an existing route. New route-table entries +
  new page components + appended pre-render list entries + appended sections only.
- **Consume, don't own, the SEO area.** Pages read the public SEO endpoints
  (`/seo/public/meta`, `/seo/public/articles`) via `lib/seo-meta.ts` at **build time**
  (never ISR, never request-time for crawlers). The per-field default-locale fallback is
  **server-side** (the site never merges locales); the coded tags —
  `canonical`/`hreflang`/`og:locale`/`inLanguage` — are **generated locally per locale** in
  `lib/head.ts` (language-invariant codes, not fetched); every locale is **pre-rendered**
  (raw-HTML per locale). The Builder never writes `seo_*` data — that is the SEO/GEO
  Optimizer's area.
- **`cms-preview` only; never publish.** Push to `cms-preview`; the SEO agent's gate decides
  go-live.
- **Match the existing site.** New pages inherit the established tokens, layout primitives,
  Motion conventions, and react-i18next setup — they must look native to the site.
