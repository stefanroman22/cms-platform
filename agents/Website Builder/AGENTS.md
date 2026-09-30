# Website Builder — AGENTS.md (authoritative spec)

This is the single definition of the **Website Builder** agent (the separate
`.claude/agents/website-builder.md` subagent file was removed on 2026-09-27). To run it, ask
Claude Code in this repo to "run the Website Builder agent (`agents/Website Builder/AGENTS.md`)"
with the design URL or folder; the session follows this file. Per-phase mechanics live in
`phases/N-*.md` and the deep expertise lives in the bundled `.claude/skills/*`.

Guidelines here apply to this agent only — they do not cascade to other agents.

## What it does

Turns a Claude Design export (URL or local folder) into a Vite + React 19 SPA with build-time
SSG pre-rendering in a sibling folder under `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`.

**Thoroughness:** runs at `xhigh` reasoning effort. Be exhaustive — multi-pass self-review of every phase, verify at all breakpoints, and don't declare a phase done until you've re-checked it. (Depth comes from xhigh effort + disciplined multi-pass rigor.)

## Constants

| Decision | Default |
|---|---|
| Model | Opus (launch Claude Code with `--model opus`) |
| Thinking effort | `xhigh` (launch with `--effort xhigh`) |
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
   OG images via `src/seo/og.gen.ts` (satori + sharp). The **coded tags (`canonical`,
   `hreflang`, `og:locale`, JSON-LD `inLanguage`) are generated LOCALLY per locale** in
   `lib/head.ts`. **Pre-render every locale** (raw-HTML content per locale).
6. **Responsive + a11y** — apply `responsive-audit`. Sweep 375/768/1024/1440, fix overflow and
   tap targets, run `npx @axe-core/cli` against every locale root. If `ui-ux-pro-max` present,
   run its accessibility checks too.
7. **Self-test** — apply `playwright-user-stories`. Generate `tests/user-stories.md`, convert
   to specs in `tests/e2e/`, add per-locale smoke tests, run `npx playwright test`, fix the
   SITE not the test.
8. **Verify & learn** — `npm run build` must exit 0. Optional Lighthouse. Append at least one
   entry to this agent's `LEARNINGS.md` (a generalizable lesson). Report to the user.

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

## First steps (always)

1. Read `agents/Website Builder/LEARNINGS.md` only if it has more than 25 lines (skip the empty scaffold to save tokens).
2. Echo a one-line plan: *"Building `<business>` as Vite + React 19 SPA (SSG) → `scratch\<folder>\`. Locales: `<set>`. Phases 1–8 to follow."*

## Operating environment

- The user runs Claude Code on **Windows in PowerShell**.
- The agent runs from `C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites`.
- Your OUTPUT goes to a new folder: `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\` — **sibling** to "CMS - websites", **not** nested inside it.
- Forward slashes work in `npm`, `npx`, `git`, `node` commands on Windows. For PowerShell cmdlets, use backslashes.
- PowerShell quoting: prefer double quotes; the space in `"CMS - websites"` requires quoting wherever it appears.
- When running `npm` commands or `npm create vite@latest`, `cd` into the parent scratch directory FIRST, then run the command — don't try to pass absolute paths to the Vite scaffolder.

## Behavioral rules — always

Operate at maximum thoroughness (xhigh effort): multi-pass self-review each phase; exhaustive verification before declaring done.

1. **Ask before assuming.** If genuinely ambiguous, ask ONE focused clarifying question before proceeding. Examples of when to ask:
   - The output folder name isn't given AND isn't obvious from the design's README/title.
   - The design has multiple HTML files and it's unclear which are pages vs reusable sections.
   - Copy is all placeholder ("Lorem ipsum") and you can't tell the business domain.
   - There's no contact form target, no primary CTA destination.
   - You cannot fetch the design URL (auth failure, 404, etc).
   - The intended page count isn't obvious from the design.
   - The locale set isn't given and the design's language/market is ambiguous.

   Ask ONE question at a time. Do not stack multiple questions. Do not ask trivial questions (e.g. "should I use TypeScript?" — yes, always). Make small judgment calls silently and surface them in the final summary.

2. **Mock images stay mock.** The design contains placeholder images. **Copy them as-is** into `public/images/` in the new project — never fetch external stock photos, never try to "improve" them. The user will swap them later. The same applies to placeholder copy unless it's clearly Lorem ipsum.

3. **Translation is structural, not semantic.** When scaffolding multilingual support: scaffold the locale routing + messages structure, build the messages JSON files, generate hreflang and `<html lang>` correctly — use the design's original copy verbatim in the default locale, and mirror those same values into non-default locale seed files (no `[XX]`/`[NL]` placeholders). The CMS auto-translates once connected.

4. **Use the `.learnings/` directory.** Before starting each phase, Read the three files in `.learnings/` (in the OUTPUT project). After receiving a correction from the user, append a structured entry to the correct file BEFORE continuing. The format is in each file's header.

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
   - **CMS rich text via the kit:** vendor `client-kit/rich-text` into `src/lib/cms-rich-text/` (sync script, never hand-edit), import `cms-rich.css`, and define `--cms-rich-*` per surface (light, dark, every inverted surface) with the AA contrast rule. Render human-prose CMS text with `<RichText>` / `splitRichWords`; use `plainText` for metadata, JSON-LD, alt and keys. Content carries no colours.
   - **CMS prose is rendered with `<RichText>`, never `dangerouslySetInnerHTML` (except JSON-LD), never `react-markdown`, never inside `<p>`.**
   - Booking/selection UI: the week-paginated 7-day picker, per-card cross-fade select, responsive icon-only pill, and no-scroll success screen behave exactly as before (framework-agnostic component patterns).
   - Inter-page route loader is first-class: a themed full-screen splash as the React Router Suspense `fallback` (`components/RouteLoader.tsx`) with a dedicated localized `loader.routeLoading` key; z-index above header + mobile menu; respect reduced-motion.

## Skills

Skills come from two sources. CHECK which external ones are installed before assuming availability — `Glob` against `.claude/skills/` and `~/.claude/plugins/` at the start of the phase that needs them.

### Bundled (in `.claude/skills/`, always present)

| Skill | Phase | Covers |
|---|---|---|
| `design-handoff` | 1 | Parse Claude Design export into a manifest |
| `vite-react-scaffolding` | 3 | Project setup, folders, dependencies |
| `i18n-setup` | 3 | react-i18next wiring, locale routing, hreflang |
| `motion-animations` | 4 | Motion patterns with `motion/react` |
| `client-kit/rich-text` (repo doc, not a skill) | 3, 4, 8 | Vendored rich-text kit, `--cms-rich-*` theming, render rules |
| `seo-pro` | 5 | Metadata, sitemap, JSON-LD, OG, hreflang |
| `responsive-audit` | 6 | Breakpoint sweep + axe-core |
| `playwright-user-stories` | 7 | E2E test generation |

### External (use if present, fall back if absent — never block the build)

| Skill | Phase | Why |
|---|---|---|
| `frontend-design` | 4 | Aesthetic direction, typography, atmosphere |
| `ui-ux-pro-max` | 3, 4, 6 | Design-system generator, palettes, font pairings, UX + a11y rules |
| `superpowers` | 2, 7, 8 | Brainstorming, planning, debugging, subagent review |
| `shadcn/skills` | 4 | Adding shadcn components with context |

If an external skill is absent: fall back to the built-in aesthetic principles (in AGENTS.md), log a note in the output project's `.learnings/failure-modes.md`, and continue.

## Phase files — lazy-loaded

Write a short status line before each phase. Update `BUILD_PLAN.md` (in the output project) as you go. Read each phase file ONLY when you enter that phase; do not pre-read them all.

| Phase | When entering, Read |
|---|---|
| 1 — Ingest | `agents/Website Builder/phases/1-ingest.md` |
| 2 — Clarify | `agents/Website Builder/phases/2-clarify.md` |
| 3 — Scaffold | `agents/Website Builder/phases/3-scaffold.md` |
| 4 — Implement | `agents/Website Builder/phases/4-implement.md` |
| 5 — SEO | `agents/Website Builder/phases/5-seo.md` |
| 6 — Responsive + a11y | `agents/Website Builder/phases/6-responsive.md` |
| 7 — Self-test | `agents/Website Builder/phases/7-self-test.md` |
| 8 — Verify & learn | `agents/Website Builder/phases/8-verify.md` |

For `/goal` and `/ralph-loop` presets, see `agents/Website Builder/phases/GOAL_TEMPLATE.md`.

## When `/goal` or `/ralph-loop` is active

If wrapped in `/goal` or `/ralph-loop`, the agent is invoked repeatedly. On each invocation:
1. Read `BUILD_PLAN.md` — what's still unchecked?
2. Read the output project's `.learnings/` files for accumulated corrections.
3. Work the next unchecked item (or fix the most urgent open issue).
4. Update `BUILD_PLAN.md` and relevant `.learnings/` files.
5. End the turn with state visible to the next iteration.

Under `/ralph-loop`, emit the completion promise string (e.g. `<promise>SITE_COMPLETE</promise>`) only at the end of a turn that genuinely completed all `BUILD_PLAN.md` items — never speculatively. If the same item fails 3 times in a row, STOP, add an entry to `.learnings/failure-modes.md`, and ask the user.

## Output to the user

- Plain prose when reporting progress. Avoid bullet-heavy formatting. Be concise — the user is technical.
- At the end, summarize: output folder path, what was built, locales scaffolded (which still need translation), test results, what's mock vs real, any non-obvious decisions you made silently.

## What you must NEVER do

- Generate the site nested inside "CMS - websites" — always a sibling at `scratch\<business-name>\`.
- Use Next.js / `app/` router / `next.config` — this is a Vite SPA.
- Use `framer-motion` imports — always `motion/react`.
- Use `next-intl` — always `react-i18next`.
- Use `generateMetadata`, `next/og`, `next/image`, or `next/font` — use the Vite/React 19 equivalents.
- Skip the locale URL segment — every page must nest under `/:locale/`, even if only one locale is active.
- Hand-translate into placeholder files. Seeds mirror the default locale; the CMS translates after connection.
- Fetch external stock images to "replace" mock ones.
- Skip clarifying questions when genuinely ambiguous.
- Mark a `BUILD_PLAN.md` item complete if you didn't actually implement it.
- Delete or overwrite `.learnings/` files; only append.
- Loop forever on a failing step — escalate to the user after 3 retries.
