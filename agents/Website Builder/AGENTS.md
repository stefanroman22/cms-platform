# Website Builder — AGENTS.md (authoritative spec)

This is the source-of-truth spec for the **website-builder** agent. The executable lives at
`.claude/agents/website-builder.md` (a Claude Code subagent, `model: claude-opus-4-8`,
`effort: xhigh`). This file documents the full workflow; per-phase mechanics live in
`phases/N-*.md` and the deep expertise lives in the bundled `.claude/skills/*`.

Guidelines here apply to this agent only — they do not cascade to other agents.

## What it does

Turns a Claude Design export (URL or local folder) into a Vite + React 19 SPA with build-time
SSG pre-rendering in a sibling folder under `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`.

**Thoroughness:** runs at `xhigh` reasoning effort. Be exhaustive — multi-pass self-review of every phase, verify at all breakpoints, and don't declare a phase done until you've re-checked it. (This is a restricted subagent: it does NOT have the Workflow/Agent tool, so it cannot fan out multi-agent work — depth comes from xhigh effort + disciplined multi-pass rigor.)

## Constants

| Decision | Default |
|---|---|
| Model | `claude-opus-4-8` (subagent frontmatter) |
| Thinking effort | `xhigh` |
| Component library | shadcn/ui (vendored) |
| Animation library | Motion (`motion/react` import) |
| i18n library | react-i18next |
| Build tool | Vite 7 + React 19 |
| SSG | vite-react-ssg |
| Router | React Router v7 (library mode) |
| Data cache | TanStack Query (localStorage-persisted) |
| App state | Zustand (persist) |
| Default locales | EN + NL |
| Locale prefix style | `always` (`/en/about`, `/nl/about`) |
| Translation strategy | Seed files mirror default locale; CMS auto-translates once connected |
| Hosting target | Static `dist/` (Vercel static or nginx Docker) |
| CMS coupling | Standalone marketing sites |
| Output folder | Sibling to "CMS - websites" at `scratch\<business-name>\` |
| Mock images | Copied from design into `public/images/<section>/`, never replaced with stock |
| Skill location | Bundled in `.claude/skills/`; externals in `~/.claude/plugins/` |
| Runtime learnings template | `agents/Website Builder/learnings-template/` |

## The 8 phases

1. **Ingest** — apply `design-handoff`. Read/fetch the export, read its README (source of
   truth for intent), identify business name, pages, tokens, sections, copy, interactions,
   locale hints. Output `_design-manifest.json` in the new project root.
2. **Clarify** — confirm output folder name, locale set, and anything genuinely ambiguous
   (one question at a time). Write `BUILD_PLAN.md` with checkboxes for every page, section,
   locale, and test.
3. **Scaffold** — apply `vite-react-scaffolding` + `i18n-setup`. Scaffold the Vite + React 19
   app, install deps, wire react-i18next, create the canonical folder structure, copy mock images
   to `public/images/<section>/`, copy `agents/Website Builder/learnings-template/*` into the
   new project's `.learnings/`. If `ui-ux-pro-max` is present, generate a tailored design
   system and reconcile with the design's tokens (design wins on conflicts).
4. **Implement** — for each section in `BUILD_PLAN.md`, build `components/sections/<name>.tsx`.
   Apply `frontend-design` + `ui-ux-pro-max` if present (else the fallback principles below).
   Wire animations via `motion-animations` (motion/react only). Use shadcn primitives. All
   strings flow through react-i18next. Check off only after the section renders for ALL locales.
5. **SEO** — apply `seo-pro`. Per-page head via `lib/head.ts` rendered as React 19 hoisted
   `<title>/<meta>/<link>` tags (baked into pre-rendered HTML by vite-react-ssg); plain
   `<meta name="viewport">`; hreflang `<link>` per locale generated locally; `src/seo/sitemap.gen.ts`
   → `public/sitemap.xml`; `src/seo/robots.gen.ts` → `public/robots.txt`; JSON-LD per page type;
   OG images via `src/seo/og.gen.ts` (satori + sharp). `lib/seo-meta.ts` fetches
   `GET /projects/{slug}/seo/public/meta?route=&locale=<locale>` at **build time** (no ISR),
   prefers stored prose, falls back to build-time output, never throws. The **coded tags
   (`canonical`, `hreflang`, `og:locale`, JSON-LD `inLanguage`) are generated LOCALLY per locale**
   in `lib/head.ts` — not fetched. The per-field default-locale fallback is SERVER-SIDE (the
   endpoint fills missing/untranslated fields; the site fetches one locale response and never
   merges locales itself). **Pre-render every locale** (raw-HTML content per locale). The
   SEO/GEO Optimizer agent owns the stored SEO area.
6. **Responsive + a11y** — apply `responsive-audit`. Sweep 375/768/1024/1440, fix overflow and
   tap targets, run `npx @axe-core/cli` against every locale root. If `ui-ux-pro-max` present,
   run its accessibility checks too.
7. **Self-test** — apply `playwright-user-stories`. Generate `tests/user-stories.md`, convert
   to specs in `tests/e2e/`, add per-locale smoke tests, run `npx playwright test`, fix the
   SITE not the test.
8. **Verify & learn** — `npm run build` must exit 0. Optional Lighthouse. Append at least one
   entry to this agent's `LEARNINGS.md` (a generalizable lesson). Report to the user.

## Incremental mode (invoked by the SEO/GEO Optimizer)

Beyond the from-scratch 8-phase build, this agent has a second mode: **add pages/sections to
an EXISTING generated site**, invoked by the **SEO/GEO Optimizer** agent (not a human, not an
initial build). The SEO agent emits a validated **`site-change-spec`** (built + validated by
`agents/SEO-GEO Optimizer/site_change_spec.py`); this agent consumes it and runs
[`phases/9-incremental.md`](./phases/9-incremental.md). Properties:

- **Additive-only** — adds a route-table entry in `src/routes.tsx` + `src/pages/<name>.tsx` +
  the locale×route pre-render entry in `src/main.tsx`; appends sections; **never** breaks or
  restructures an existing route, never a full rebuild.
- **SEO-area-aware** — generated pages consume the public SEO endpoints for every pre-render
  locale: `lib/head.ts` + `lib/seo-meta.ts` fetch
  `GET /projects/{slug}/seo/public/meta?route=&locale=<locale>` at **build time** (prefers
  stored prose, falls back, never throws). `consumes: seo_articles` pages fetch
  `GET /projects/{slug}/seo/public/articles` for a `/blog` index + `/blog/:slug` routes whose
  pre-render list is generated from article slugs fetched at build time; client refetch keeps
  content fresh for humans. The **per-field default-locale fallback is server-side** (the site
  never merges locales); the **coded tags — canonical/hreflang/og:locale/inLanguage — are
  generated locally per locale** in `lib/head.ts`. **Pre-render every locale** (raw-HTML content
  per locale). The Builder consumes — it never writes the `seo_*` area (the SEO/GEO Optimizer
  owns it).
- **`cms-preview` only, never publishes** — pushes the additive routes to `cms-preview` and
  hands back to the SEO agent's Phase-6 visual-QA gate (a `pre-render` content-in-raw-HTML
  check), which publishes only when all-green. A publish triggers the rebuild hook (Plan B).
- Each new page meets the same bar as a from-scratch page (full `seo-pro` metadata,
  responsive, Motion, per-locale i18n, Playwright smoke).

## Built-in aesthetic principles (fallback if `frontend-design` and `ui-ux-pro-max` absent)

- **Pick a clear aesthetic direction** before coding (brutally minimal, editorial, refined/
  luxury, organic, retro-futuristic, playful). Commit and execute precisely.
- **Typography**: avoid Inter/Roboto/Arial/system-ui for the display font (reads as "AI
  default"). Pair a distinctive display font with a refined body via `@fontsource*` + CSS
  `@import` (e.g. Fraunces, Instrument Serif, Cabinet Grotesk + Inter, Geist Sans, IBM Plex
  Sans). NEVER `next/font`.
- **Color**: a dominant color with sharp accents beats timid, evenly-distributed palettes.
  Avoid purple-gradient-on-white.
- **Motion**: high-impact moments > scattered micro-interactions.
- **Spatial composition**: unexpected layouts, asymmetry, generous negative space OR
  controlled density — not the predictable centered column.
- **Atmosphere**: gradient meshes, noise textures, layered transparencies, dramatic shadows.

## Known implementation gotchas (must-handle)

- **SPA mount + translation shim in `index.html`.** `index.html` is the SPA entry: it holds
  `<html>`/`<body>`, the SPA mount `<div id="root">`, and the translation-resilience shim as the
  FIRST inline `<script>` (before the module script). The shim patches
  `Node.prototype.removeChild`/`insertBefore`: when `child.parentNode !== this`, operate on the
  actual parent instead of throwing (in-browser translators reparent text nodes into `<font>`
  wrappers; without the shim, React's commit-phase DOM ops throw `NotFoundError` and can unmount
  the root). Do NOT patch `replaceChild`. Add `suppressHydrationWarning` on `<html>` (covers
  translator `lang`/`class` mutation on the SSG-hydrated path).
- **Env / CORS / dev-origin.** Client fetches need `VITE_*` base URLs in `.env.local`, and
  GUARD a missing base (never fetch `"undefined/..."`). A separate-origin backend must allow
  `http://localhost:<port>` in its CORS allowlist (or proxy same-origin via a Vite proxy). Open
  dev at the Vite-printed origin (usually `http://localhost:5173`), not a different port.
- **Week-paginated day picker.** Fetch availability per VISIBLE week (lazy), refetch on prev/next
  arrow nav, and reset to week 0 when the service/barber changes; render all 7 cells in a
  `grid repeat(7,1fr)` (no horizontal scroll), disable sold-out days, and slide weeks directionally
  via `AnimatePresence` keyed on the week offset (reduced-motion → fade).
- **Selection cross-fade.** Service/barber cards select via a stacked `+`/check cross-fade
  (opacity + scale) with the colour/border transitioning — animate the checkmark in, never pop it
  (reduced-motion disables it).
- **Responsive selectable pill.** An `avatar | text | pill` card with a `flex:0 0 auto` pill crushes
  the text on phones — collapse the pill to an icon-only badge (hide its label) and set `min-width:0`
  on the text column below the breakpoint; keep the labelled pill on desktop.
- **No-scroll success screen.** The confirmation screen must fit fully without scrolling on every
  viewport (320→1440): compact centred layout, `@media (max-height)` tiers shrinking type/spacing,
  drop only the least-important secondary line on tiny legacy phones (≤360w AND ≤600h). The "manage
  your booking" link is its OWN themed hover-able accent link, distinct from the "Date & time" label.
- **Route loader (`loader.routeLoading`).** Use a full-screen themed splash (wordmark + spinner +
  a short business-flavoured status line) as the React Router Suspense `fallback`
  (`components/RouteLoader.tsx`) with a DEDICATED i18n key `loader.routeLoading` — not the intro
  loader's copy; z-index above the header/mobile menu; respect reduced-motion.

## Self-improvement

- This agent's own cross-build lessons live in `LEARNINGS.md` (append-only). Phase 8 adds at
  least one entry per build.
- Each generated site gets its own `.learnings/` (seeded from `learnings-template/`) for
  per-build corrections, failure modes, and conventions.
- When a build teaches a generalizable rule, append it to BOTH the generated project's
  `.learnings/conventions.md` AND `agents/Website Builder/learnings-template/conventions.md` so
  future builds inherit it.
