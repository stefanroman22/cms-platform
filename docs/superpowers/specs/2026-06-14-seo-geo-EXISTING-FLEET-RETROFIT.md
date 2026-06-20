# SEO/GEO — Existing-Fleet Retrofit Runbook (follow-up)

**Date:** 2026-06-14
**Status:** FOLLOW-UP — NOT done by Plan 4. This is a per-site operation to run later.
**Scope:** retrofit the EXISTING generated sites — **samir-kapsalon**,
**laurian-duma-portfolio**, **it-global-services** — to CONSUME the SEO/GEO area.

---

## Why this exists

Plan 4 made the cross-agent SEO consumption **contract** real and wired it into the
production agent specs (Website Builder incremental mode, CMS Connector SEO-area wiring,
`seo-pro` de-myth, the SEO agent's phase 7). So **every FUTURE connector run** produces a
site whose `generateMetadata` prefers stored `seo_page_meta` and whose `/blog` reads
`seo_articles`.

The **existing** sites were generated **before** that consumption contract existed. Their
`generateMetadata` reads only build-time `seo-pro` output, and none has a `/blog` wired to
`seo_articles`.

> **Consequence until retrofitted:** when the SEO/GEO Optimizer agent runs against one of
> these three sites and publishes `seo_page_meta` (or `seo_articles`), that data lives in the
> **CMS + the dashboard "SEO & GEO" section** (client + admin can read/edit/delete it) — but
> it does **NOT yet affect that live site**. The live site keeps serving its build-time
> metadata until the site is retrofitted to consume the public SEO endpoints.

This retrofit is a **manual / connector-re-run operation**, intentionally OUT of Plan 4's
scope (Plan 4 does not edit any live client repo). Run it per site when you want a given
existing site to actually serve the agent's stored SEO.

---

## Per-site procedure

Repeat for each of `samir-kapsalon`, `laurian-duma-portfolio`, `it-global-services`. The
cleanest path is a **CMS Connector re-run** (it now performs §4.1.7 SEO-area wiring); the
manual steps below are equivalent if you wire by hand.

1. **Base the work on `origin/cms-preview`.** Local client repos are often several commits
   behind their deployed origin — fetch + base on `origin/cms-preview` before editing (see the
   Connector LEARNINGS note). Never trust a stale local working copy.

2. **Add `lib/seo-meta.ts`** (mirrors `lib/cms-content.ts`: ISR + never-throw fallback). It
   fetches `GET {backend}/projects/{slug}/seo/public/meta?route=<route>&locale=<locale>` with
   `next: { revalidate: 60 }`, returns `null` on any non-ok/error (so callers fall back to the
   build-time `seo-pro` metadata), and NEVER throws.

3. **Wire `generateMetadata` to prefer stored meta.** In each page's `generateMetadata`, call
   the helper first; when it returns stored `title`/`description`/`canonical`/`og`/`json_ld`,
   use those (PREFER stored over build-time); otherwise keep the existing `seo-pro` output.

4. **(Optional) Add `/blog` if articles exist.** Only if the SEO agent has created
   `seo_articles` for the site: add a `/blog` index + `/blog/[slug]` that fetch
   `GET {backend}/projects/{slug}/seo/public/articles?locale=<locale>` (+ `/{articleSlug}`),
   ISR + fallback, and set `projects.seo_blog_route = '/blog'`. New routes are additive — do
   not restructure existing routes. (The Website Builder incremental mode can add these from a
   `site-change-spec` instead of hand-coding.)

5. **Push to `cms-preview`.** Commit the additive wiring and push to the site's `cms-preview`
   branch. Do NOT push to the production branch directly.

6. **Run the SEO agent's visual-QA gate.** Have the SEO/GEO Optimizer (or `seo-visual-qa`
   directly) render the affected routes × locales at 375/768/1440 on cms-preview / the Vercel
   preview — responsive / visibility / no-crash / no-console-error / build-ok / links-resolve /
   content-in-raw-HTML. Self-heal bounded; do not proceed if it can't go green.

7. **Promote.** On an all-green gate, promote `cms-preview` → the production branch (the
   Connector promotion path). The site now serves the agent's stored `seo_page_meta` (and
   `/blog` from `seo_articles` if wired).

---

## Done criteria (per site)

- `lib/seo-meta.ts` present; `generateMetadata` prefers stored `seo_page_meta` with a static
  fallback (never throws).
- If the site has `seo_articles`: `/blog` index + `/blog/[slug]` consume
  `seo/public/articles`; `projects.seo_blog_route` set.
- The visual-QA gate is green; `cms-preview` promoted to production.
- A spot-check confirms: edit a route's meta in the dashboard "SEO & GEO" section → publish →
  the live page's `<title>`/`<meta description>` reflect it within the ISR window.

## Notes

- This runbook does NOT change Plan 4's deliverables; it is the explicit follow-up the plan's
  scope boundary calls out.
- Prefer the **Connector re-run** path where possible — it applies §4.1.7 SEO-area wiring
  consistently and keeps the generated-site contract in one place.
