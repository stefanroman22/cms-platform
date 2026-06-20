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
existing `app/[locale]/…` routing, next-intl messages, design tokens, and section component
conventions.

## Steps

1. **Read the spec + the existing site.** Parse the `site-change-spec`. Inspect the existing
   `app/[locale]/` routing, the next-intl `messages/<locale>.json`, the design tokens, and the
   existing section components — the new pages must MATCH the site's established aesthetic,
   layout primitives, and i18n conventions. Confirm `branch == "cms-preview"`.

2. **For each `page`, add `app/[locale]/<route>/page.tsx`** (additive — never overwrite an
   existing route):
   - Full **`seo-pro`** metadata: `generateMetadata` per locale, `alternates.languages`
     hreflang, JSON-LD of `schema_type`, OG. `generateMetadata` **prefers stored
     `seo_page_meta`** for the **active** locale: fetch
     `GET /projects/{slug}/seo/public/meta?route=<route>&locale=<active-locale>` and use the
     stored **prose** (title/description/OG text + JSON-LD data), falling back to the build-time
     `seo-pro` output (ISR ~60s; **never throw** — fall back on any error). The **per-field
     default-locale fallback is SERVER-SIDE** — the endpoint fills any missing/untranslated
     locale field from the default-locale row, so the page fetches one active-locale response
     and **never merges locales itself**. The **coded tags are generated LOCALLY per locale** —
     `canonical`, `hreflang` (`alternates.languages`), `og:locale`, and JSON-LD `inLanguage` are
     language-invariant codes, NOT fetched. **SSR every locale** (raw-HTML content per locale —
     AI/Google bots don't run JS).
   - Responsive at 375/768/1024/1440 + Motion (`motion/react`) + real section components built
     from the design tokens (not placeholders).
   - **`consumes: "seo_articles"`** → the page fetches
     `GET /projects/{slug}/seo/public/articles?locale=<active-locale>` (blog index) and
     `…/articles/{articleSlug}` (post), ISR + never-throw fallback, and renders the list/post.
     An untranslated article transparently shows default-locale prose (server-side per-field
     fallback) — the page does not merge.
   - **`consumes: "seo_page_meta"`** → as above, `generateMetadata` reads `/seo/public/meta`.
   - **`consumes: "static"` / `None`** → no remote fetch; render from the design content.

3. **For each `section`,** add the `component` to `target_route`'s page additively (append a
   section; do not restructure the existing page), with its `schema_type` JSON-LD where given.

4. **Nav + i18n.** For each page with `nav.add: true`, add the nav entry using `nav.label_i18n`
   as the message key, and add that key (+ every other new string) to **every** locale's
   `messages/<locale>.json`. No hard-coded strings — all copy flows through next-intl.

5. **Per-locale Playwright smoke.** Run the existing `playwright-user-stories` smoke plus a
   smoke for each NEW route × locale (renders, no console error, links resolve). Fix the SITE,
   not the test. The from-scratch phases 5–7 bar applies to the new pages.

6. **Push to `cms-preview`.** Commit the additive changes and push to the `cms-preview` branch
   (the spec's `branch`). Do **NOT** push to the production branch and do **NOT** publish — the
   SEO/GEO Optimizer promotes to production only after its gate is green.

7. **Hand back to the SEO agent's Phase-6 gate.** Return control to the SEO/GEO Optimizer,
   which runs the **`seo-visual-qa`** gate (375/768/1440 per locale, responsive / visibility /
   no-crash / no-console-error / build-ok / links-resolve / content-in-raw-HTML) over the new
   routes and publishes only when all-green (else halt + revert). This Builder mode never
   publishes by itself.

## Outputs

- New additive `app/[locale]/<route>/page.tsx` (+ any `sections`) on the `cms-preview` branch,
  each with full `seo-pro` metadata that **prefers stored `seo_page_meta`**, the `seo_articles`
  consumption where specified, nav entries + per-locale i18n keys, and a green per-locale
  Playwright smoke. No existing route changed. Nothing published — handed back to the SEO
  agent's Phase-6 gate.

## Hard rules (incremental mode)

- **Additive only.** Never break or restructure an existing route. New `page.tsx` files +
  appended sections only.
- **Consume, don't own, the SEO area.** Pages read the public SEO endpoints
  (`/seo/public/meta`, `/seo/public/articles`) **for the active locale** with ISR +
  never-throw fallback. The per-field default-locale fallback is **server-side** (the site
  never merges locales); the coded tags — `canonical`/`hreflang`/`og:locale`/`inLanguage` — are
  **generated locally per locale** (language-invariant codes, not fetched), and every locale is
  SSR'd. The Builder never writes `seo_*` data — that is the SEO/GEO Optimizer's area.
- **`cms-preview` only; never publish.** Push to `cms-preview`; the SEO agent's gate decides
  go-live.
- **Match the existing site.** New pages inherit the established tokens, layout primitives,
  Motion conventions, and next-intl setup — they must look native to the site.
