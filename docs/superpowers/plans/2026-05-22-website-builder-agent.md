# Website Builder Agent Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the downloaded `website-builder-agent` package into this repo as a first-class agent — repo-convention docs in `agents/Website Builder/` plus the real Claude Code subagent at `.claude/agents/website-builder.md` and 7 bundled skills at `.claude/skills/`.

**Architecture:** The `agents/Website Builder/` folder is source-of-truth documentation (AGENTS.md + README + LEARNINGS + thin per-phase orchestration files + the runtime learnings-template). The executable is the real subagent (`model: claude-opus-4-7`, `effort: high`) which lazy-loads phase files and applies the 7 skills. Phase logic is never duplicated: skills hold the deep "HOW", phase files hold thin orchestration, the subagent holds frontmatter + hard rules.

**Tech Stack:** Markdown agent/skill files (Claude Code subagent + skills format). No application code. Source package at `C:\Users\stefa\Downloads\website-builder-agent`.

---

## File Structure

**Verbatim copies (no edits):**
- `C:\Users\stefa\Downloads\website-builder-agent\skills\*` → `.claude/skills/*` (7 skills)
- `...\learnings-template\*` → `agents/Website Builder/learnings-template/*` (3 files)
- `...\GOAL_TEMPLATE.md` → `agents/Website Builder/phases/GOAL_TEMPLATE.md`

**Authored / adapted (full content in tasks below):**
- `.claude/agents/website-builder.md` — subagent, adapted (lazy phase table + learnings-template path fix)
- `agents/Website Builder/AGENTS.md` — authoritative spec
- `agents/Website Builder/phases/1-ingest.md` … `8-verify.md` — thin orchestration
- `agents/Website Builder/README.md` — quick reference
- `agents/Website Builder/example-prompts.md` — adapted from package
- `agents/Website Builder/LEARNINGS.md` — empty scaffold

**Modified:**
- `agents/README.md` — append one catalog row

---

## Task 1: Create directories and copy the 7 bundled skills verbatim

**Files:**
- Create dir: `.claude/skills/{design-handoff,nextjs-app-scaffolding,i18n-setup,seo-pro,responsive-audit,motion-animations,playwright-user-stories}/`
- Create dir: `agents/Website Builder/{phases,learnings-template}/`

- [ ] **Step 1: Create the directory tree**

Run (PowerShell, from repo root):
```powershell
$repo = "C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites"
New-Item -ItemType Directory -Force -Path "$repo\agents\Website Builder\phases" | Out-Null
New-Item -ItemType Directory -Force -Path "$repo\agents\Website Builder\learnings-template" | Out-Null
New-Item -ItemType Directory -Force -Path "$repo\.claude\agents" | Out-Null
New-Item -ItemType Directory -Force -Path "$repo\.claude\skills" | Out-Null
```

- [ ] **Step 2: Copy the 7 skills verbatim**

Run:
```powershell
$pkg = "C:\Users\stefa\Downloads\website-builder-agent"
$repo = "C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites"
foreach ($s in @("design-handoff","nextjs-app-scaffolding","i18n-setup","seo-pro","responsive-audit","motion-animations","playwright-user-stories")) {
  New-Item -ItemType Directory -Force -Path "$repo\.claude\skills\$s" | Out-Null
  Copy-Item -Path "$pkg\skills\$s\*" -Destination "$repo\.claude\skills\$s\" -Recurse -Force
}
```

- [ ] **Step 3: Verify all 7 SKILL.md landed with matching `name:`**

Run:
```powershell
Get-ChildItem "$repo\.claude\skills" -Directory | ForEach-Object {
  $f = Join-Path $_.FullName "SKILL.md"
  "$($_.Name): " + (Test-Path $f)
}
```
Expected: 7 lines, all ending `True`, including the 4 pre-existing skills (cms-connector-website, design-prompt-creator, lead-to-design-prompt, solver-issues) plus the 7 new ones = 11 dirs total. Confirm the 7 new ones print `True`.

- [ ] **Step 4: Copy the learnings-template (3 files) verbatim**

Run:
```powershell
Copy-Item -Path "$pkg\learnings-template\*" -Destination "$repo\agents\Website Builder\learnings-template\" -Force
```

- [ ] **Step 5: Copy GOAL_TEMPLATE.md into the agent's phases folder**

Run:
```powershell
Copy-Item -Path "$pkg\GOAL_TEMPLATE.md" -Destination "$repo\agents\Website Builder\phases\GOAL_TEMPLATE.md" -Force
```

- [ ] **Step 6: No commit** (per standing repo rule — Stefan commits explicitly).

---

## Task 2: Author the subagent `.claude/agents/website-builder.md`

This is the package's `agents/website-builder.md` adapted: the 8-phase prose is replaced by a **lazy phase-loading table** pointing at `agents/Website Builder/phases/N.md`, and the learnings-template path is fixed to the agent-owned location. Frontmatter, behavioral rules, hard constraints, and the NEVER list are preserved verbatim.

**Files:**
- Create: `.claude/agents/website-builder.md`

- [ ] **Step 1: Write the file with this exact content**

```markdown
---
name: website-builder
description: Builds production-ready, multilingual Next.js 16 websites from Claude Design exports. Use whenever the user wants to implement a design from Claude Design (or any handoff folder containing HTML/CSS/assets) as a real Next.js + Tailwind + Motion application with i18n, SEO, responsiveness, and Playwright self-testing. Triggers on phrases like "implement this design", "build the site from", "fetch this design and implement", or any reference to a Claude Design URL or design export folder.
tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch
model: claude-opus-4-7
effort: high
---

# Website Builder Agent

You are the **website-builder** subagent. Your job: take a Claude Design export (URL or local folder) and produce a production-quality, multilingual Next.js 16 website in a new sibling folder.

## First steps (always)

1. Read `agents/Website Builder/AGENTS.md` — the authoritative workflow spec + constants table.
2. Read `agents/Website Builder/LEARNINGS.md` only if it has more than 25 lines (skip the empty scaffold to save tokens).
3. Echo a one-line plan: *"Building `<business>` → `scratch\<folder>\`. Locales: `<set>`. Phases 1–8 to follow."*

## Operating environment

- The user runs Claude Code on **Windows in PowerShell**.
- You are invoked from `C:\Users\stefa\.gemini\antigravity\scratch\CMS - websites`.
- Your OUTPUT goes to a new folder: `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\` — **sibling** to "CMS - websites", **not** nested inside it.
- Forward slashes work in `npm`, `npx`, `git`, `node` commands on Windows. For PowerShell cmdlets, use backslashes.
- PowerShell quoting: prefer double quotes; the space in `"CMS - websites"` requires quoting wherever it appears.
- When running `npm` commands or `npx create-next-app`, `cd` into the parent scratch directory FIRST, then run the command — don't try to pass absolute paths to `create-next-app`.

## Behavioral rules — always

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

3. **Translation is structural, not semantic.** When scaffolding multilingual support: create the locale routing, build the messages JSON files, generate hreflang and `<html lang>` correctly — but use the design's original copy verbatim in the default locale, and put `[locale-code] <original>` placeholders in the other locale files (e.g. `[NL] Welcome to Acme`). DO NOT auto-translate copy. The user does that pass separately, often through their existing n8n translation flow.

4. **Use the `.learnings/` directory.** Before starting each phase, Read the three files in `.learnings/` (in the OUTPUT project). After receiving a correction from the user, append a structured entry to the correct file BEFORE continuing. The format is in each file's header.

5. **Hard constraints — never violate:**
   - Animation library is **`motion`** (`import { motion } from "motion/react"`). NEVER `framer-motion`. NEVER `import from "motion"` (the React entry is `motion/react`).
   - i18n library is **`next-intl`**, not `next-i18next` (deprecated for App Router) or `react-i18next` (doesn't integrate with App Router routing).
   - All metadata uses Next.js Metadata API. `themeColor`, `viewport`, `width`, `initialScale` go in the `viewport` export, NOT `metadata`. (Breaking change since Next 15.)
   - All clickable elements have accessible names. All images have `alt`. All forms have labels.
   - Mobile-first. Verify at 375 / 768 / 1024 / 1440 before declaring done.
   - Use `next/image` not `<img>` (except inside `next/og` ImageResponse).
   - Use `next/font` not `<link rel="stylesheet">` for fonts.
   - NEVER use `localStorage` / `sessionStorage` in this codebase — SSR breaks. Persist via API routes or cookies if needed.
   - Locale routing: `app/[locale]/...` pattern. Every page lives under `[locale]`.

## Skills

Skills come from two sources. CHECK which external ones are installed before assuming availability — `Glob` against `.claude/skills/` and `~/.claude/plugins/` at the start of the phase that needs them.

### Bundled (in `.claude/skills/`, always present)

| Skill | Phase | Covers |
|---|---|---|
| `design-handoff` | 1 | Parse Claude Design export into a manifest |
| `nextjs-app-scaffolding` | 3 | Project setup, folders, dependencies |
| `i18n-setup` | 3 | next-intl wiring, locale routing, hreflang |
| `motion-animations` | 4 | Motion patterns with `motion/react` |
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

## The 8-phase workflow — lazy-loaded

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

If wrapped in `/goal` or `/ralph-loop`, you'll be invoked repeatedly. On each invocation:
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
- Use `framer-motion` imports — always `motion/react`.
- Use `next-i18next` or `react-i18next` — always `next-intl`.
- Auto-translate copy. Translation placeholders only; user does the real pass.
- Fetch external stock images to "replace" mock ones.
- Skip clarifying questions when genuinely ambiguous.
- Mark a `BUILD_PLAN.md` item complete if you didn't actually implement it.
- Delete or overwrite `.learnings/` files; only append.
- Use `pages/` directory — App Router only.
- Use `<img>` outside of `next/og` ImageResponse.
- Loop forever on a failing step — escalate to the user after 3 retries.
- Skip locale routing — every page must live under `app/[locale]/`, even if only one locale is active.
```

- [ ] **Step 2: Verify frontmatter is well-formed**

Run:
```powershell
Get-Content "$repo\.claude\agents\website-builder.md" -TotalCount 7
```
Expected: line 1 is `---`, includes `name: website-builder`, `model: claude-opus-4-7`, `effort: high`, `tools: Read, Write, Edit, Bash, Glob, Grep, WebFetch`.

---

## Task 3: Author `agents/Website Builder/AGENTS.md`

The authoritative human-readable spec. Holds the constants table, the built-in aesthetic fallback principles, and the canonical 8-phase descriptions (the package's prose). The subagent points here; phase files expand each step.

**Files:**
- Create: `agents/Website Builder/AGENTS.md`

- [ ] **Step 1: Write the file with this exact content**

```markdown
# Website Builder — AGENTS.md (authoritative spec)

This is the source-of-truth spec for the **website-builder** agent. The executable lives at
`.claude/agents/website-builder.md` (a Claude Code subagent, `model: claude-opus-4-7`,
`effort: high`). This file documents the full workflow; per-phase mechanics live in
`phases/N-*.md` and the deep expertise lives in the bundled `.claude/skills/*`.

Guidelines here apply to this agent only — they do not cascade to other agents.

## What it does

Turns a Claude Design export (URL or local folder) into a production-grade, multilingual
Next.js 16 site in a sibling folder under `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`.

## Constants

| Decision | Default |
|---|---|
| Model | `claude-opus-4-7` (subagent frontmatter) |
| Thinking effort | `high` |
| Component library | shadcn/ui (vendored) |
| Animation library | Motion (`motion/react` import) |
| i18n library | next-intl |
| Default locales | EN + NL |
| Locale prefix style | `always` (`/en/about`, `/nl/about`) |
| Translation strategy | Placeholders only (`[NL] ...`); user translates separately |
| Hosting target | Vercel-compatible with `output: 'standalone'` for Hetzner Docker |
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
3. **Scaffold** — apply `nextjs-app-scaffolding` + `i18n-setup`. Scaffold the Next.js app,
   install deps, wire next-intl, create the canonical folder structure, copy mock images to
   `public/images/<section>/`, copy `agents/Website Builder/learnings-template/*` into the
   new project's `.learnings/`. If `ui-ux-pro-max` is present, generate a tailored design
   system and reconcile with the design's tokens (design wins on conflicts).
4. **Implement** — for each section in `BUILD_PLAN.md`, build `components/sections/<name>.tsx`.
   Apply `frontend-design` + `ui-ux-pro-max` if present (else the fallback principles below).
   Wire animations via `motion-animations` (motion/react only). Use shadcn primitives. All
   strings flow through next-intl. Check off only after the section renders for ALL locales.
5. **SEO** — apply `seo-pro`. `generateMetadata` per locale, separate `viewport` export,
   `alternates.languages` hreflang, `app/sitemap.ts`, `app/robots.ts`, JSON-LD per page type,
   OG images.
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
  default"). Pair a distinctive display font with a refined body via `next/font/google`
  (e.g. Fraunces, Instrument Serif, Cabinet Grotesk + Inter, Geist Sans, IBM Plex Sans).
- **Color**: a dominant color with sharp accents beats timid, evenly-distributed palettes.
  Avoid purple-gradient-on-white.
- **Motion**: high-impact moments > scattered micro-interactions.
- **Spatial composition**: unexpected layouts, asymmetry, generous negative space OR
  controlled density — not the predictable centered column.
- **Atmosphere**: gradient meshes, noise textures, layered transparencies, dramatic shadows.

## Self-improvement

- This agent's own cross-build lessons live in `LEARNINGS.md` (append-only). Phase 8 adds at
  least one entry per build.
- Each generated site gets its own `.learnings/` (seeded from `learnings-template/`) for
  per-build corrections, failure modes, and conventions.
- When a build teaches a generalizable rule, append it to BOTH the generated project's
  `.learnings/conventions.md` AND `learnings-template/conventions.md` so future builds inherit it.
```

- [ ] **Step 2: Verify it references the agent-owned learnings-template path**

Run:
```powershell
Select-String -Path "$repo\agents\Website Builder\AGENTS.md" -Pattern "learnings-template" -SimpleMatch
```
Expected: at least 2 hits, all using `agents/Website Builder/learnings-template/` or the bare relative `learnings-template/` under the agent folder — none pointing at repo root.

---

## Task 4: Author the 8 thin phase files

Each is thin orchestration: what to apply, what artifact to produce, what gate to pass. They point at the skill; they do NOT re-explain it.

**Files:**
- Create: `agents/Website Builder/phases/1-ingest.md` … `8-verify.md`

- [ ] **Step 1: Write `phases/1-ingest.md`**

```markdown
# Phase 1 — Ingest

**Apply skill:** `design-handoff` (in `.claude/skills/design-handoff/`).

**Do:**
- Read or WebFetch the Claude Design export (URL or local folder).
- Read the design's `README.md` if present — highest-priority source of intent.
- Extract: business name, page list, design tokens (color/type/spacing/radii/shadows),
  sections per page, copy, intended interactions, locale hints, responsive gaps.

**Produce:** `_design-manifest.json` in the new project root (schema in the skill).
For URL sources, cache fetched assets to `_design-cache/`.

**Gate:** Manifest exists and is valid JSON. If intent was thin (no README), the manifest's
`notes` array says so. If anything was genuinely ambiguous, you asked exactly one question.

**Token tactics:** Read README + index.html + CSS; sample asset names, don't open every image.
```

- [ ] **Step 2: Write `phases/2-clarify.md`**

```markdown
# Phase 2 — Clarify

**No skill.** Behavioral. If `superpowers` is installed and requirements are genuinely fuzzy,
you may use `superpowers:brainstorming`; otherwise ask the user directly.

**Do:**
- Confirm output folder name (default: kebab-cased business name).
- Confirm locale set (default: EN + NL).
- Confirm anything genuinely ambiguous — ONE question at a time, no stacking, no trivia.

**Produce:** `BUILD_PLAN.md` in the new project root with checkboxes for every page, every
section, every locale, and every planned test.

**Gate:** `BUILD_PLAN.md` exists with concrete checkboxes (not placeholders). Folder name and
locale set are settled.
```

- [ ] **Step 3: Write `phases/3-scaffold.md`**

```markdown
# Phase 3 — Scaffold

**Apply skills:** `nextjs-app-scaffolding` + `i18n-setup`.

**Do:**
- `cd` to the parent scratch directory FIRST, then `npx create-next-app@latest <folder>` with
  the flags in the scaffolding skill.
- Install Motion, next-intl, lucide-react, shadcn/ui, Playwright (per the skill).
- Wire next-intl: `i18n/routing.ts`, `request.ts`, `navigation.ts`, `middleware.ts`,
  `createNextIntlPlugin` in `next.config.ts`, messages files (`[XX]` placeholders for
  non-default locales).
- Set fonts via `next/font` in `app/[locale]/layout.tsx`.
- Create the canonical folder structure.
- Copy the design's mock images to `public/images/<section>/<filename>`.
- Copy `agents/Website Builder/learnings-template/*` into the new project's `.learnings/`.
- If `ui-ux-pro-max` is installed, run its design-system generator and reconcile with the
  manifest tokens — the design wins on direct conflicts; ui-ux-pro-max fills gaps.

**Gate:** `npm run dev` boots; `/` redirects to `/<default-locale>`; `.learnings/` has all
three template files; mock images are in place.

**Token tactics:** don't echo full create-next-app output; summarize success/failure.
```

- [ ] **Step 4: Write `phases/4-implement.md`**

```markdown
# Phase 4 — Implement

**Apply skill:** `motion-animations` (motion/react only). Use external `frontend-design` and
`ui-ux-pro-max` if present (Glob to check); else use the aesthetic fallback in AGENTS.md.

**Do, per section in `BUILD_PLAN.md`:**
- Build `components/sections/<name>.tsx`.
- Apply aesthetic direction (frontend-design) + section-type UX rules (ui-ux-pro-max).
- Add shadcn components via `shadcn/skills` if present, else `npx shadcn@latest add <c>`.
- Wire Motion via `components/motion/` wrappers — `motion/react` import only.
- All UI strings via next-intl `useTranslations()` / `getTranslations()` — never hardcoded.
- Mobile-first Tailwind (default = mobile; `md:`/`lg:`/`xl:` upscale).

**Gate:** Check off a `BUILD_PLAN.md` item ONLY after the section renders correctly for ALL
locales. Run the motion-animations grep: zero `framer-motion` matches.
```

- [ ] **Step 5: Write `phases/5-seo.md`**

```markdown
# Phase 5 — SEO

**Apply skill:** `seo-pro`.

**Do:**
- Root metadata in `app/[locale]/layout.tsx` via `generateMetadata` (locale-specific
  titles/descriptions). `viewport` exported SEPARATELY (Next 15+ breaking change).
- `alternates.languages` hreflang for every locale on every page.
- `app/sitemap.ts` (every locale × every page, with hreflang alternates), `app/robots.ts`.
- JSON-LD per page type (Organization/LocalBusiness on home; appropriate type elsewhere),
  honoring the current locale's name/description.
- `app/opengraph-image.tsx` (+ per-locale variants if locales differ significantly).
- Set real `metadataBase` (ask for the domain if unknown) — never leave `example.com`.

**Gate:** `npm run build` shows no metadata warnings; `/sitemap.xml` and `/robots.txt` render;
JSON-LD validates at validator.schema.org.
```

- [ ] **Step 6: Write `phases/6-responsive.md`**

```markdown
# Phase 6 — Responsive + a11y

**Apply skill:** `responsive-audit`. Use Playwright MCP for screenshots if available.

**Do:**
- Sweep 375 / 768 / 1024 / 1440 (375 + 768 catch ~95%). Fix horizontal overflow, cut-off
  content, tap targets < 44px, non-scaling images, hover-only interactions.
- Apply container queries where component-internal responsiveness beats viewport-level.
- Run `npx @axe-core/cli` against every locale root (`/en`, `/nl`, …) — fix every violation.
- If `ui-ux-pro-max` present, run its accessibility checks and apply applicable rules.

**Gate:** No overflow at any breakpoint; axe-core reports 0 violations on every page; every
resolved `responsive_gaps` item from the manifest has a matching `.learnings/` entry.
```

- [ ] **Step 7: Write `phases/7-self-test.md`**

```markdown
# Phase 7 — Self-test

**Apply skill:** `playwright-user-stories`.

**Do:**
- Generate `tests/user-stories.md` from `_design-manifest.json`.
- Convert each story to a spec in `tests/e2e/<page>.spec.ts` (accessibility-first selectors).
- Add per-locale smoke tests: each locale root loads, `/` redirects to default locale,
  `<html lang>` matches URL, language switcher preserves path, hreflang tags present.
- Use `127.0.0.1` (not `localhost`) in `playwright.config.ts` baseURL (Windows IPv6 issue).
- Run `npx playwright test`. Fix the SITE, not the test (unless the test is wrong). Never
  weaken assertions to pass.
- If `superpowers` present and the project is non-trivial, consider its subagent-driven
  two-stage review on the generated suite before running.

**Gate:** `npx playwright test` exits 0. If the same test fails 3× with the same root cause,
STOP and ask the user.
```

- [ ] **Step 8: Write `phases/8-verify.md`**

```markdown
# Phase 8 — Verify & learn

**No skill.** Runs commands + records lessons.

**Do:**
- `npm run build` — must exit 0 (no TypeScript or build errors).
- Optionally `npx unlighthouse-ci --site http://127.0.0.1:3000`; note scores in `BUILD_PLAN.md`.
- Final grep gates: zero `framer-motion`, zero `next-i18next`/`react-i18next`, zero raw `<img `
  outside `app/opengraph-image.tsx` / `app/og/`.
- If a build/test failure is hard to diagnose and `superpowers` is installed, use its debugging
  methodology (root-cause-first).
- Append at least one generalizable lesson to `agents/Website Builder/LEARNINGS.md`. If the
  lesson should apply to every future build, also append it to `learnings-template/conventions.md`.

**Report to the user:** output folder path, what was built, locales scaffolded (which still need
translation), test results, what's mock vs real, any silent judgment calls.
```

- [ ] **Step 9: Verify all 8 phase files exist**

Run:
```powershell
Get-ChildItem "$repo\agents\Website Builder\phases" -Name | Sort-Object
```
Expected: `1-ingest.md`, `2-clarify.md`, `3-scaffold.md`, `4-implement.md`, `5-seo.md`, `6-responsive.md`, `7-self-test.md`, `8-verify.md`, `GOAL_TEMPLATE.md`.

---

## Task 5: Author `README.md` and `example-prompts.md`

**Files:**
- Create: `agents/Website Builder/README.md`
- Create: `agents/Website Builder/example-prompts.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# Website Builder — quick reference

Claude Code subagent that turns a Claude Design export into a production-ready, multilingual
Next.js 16 site in a sibling folder under `scratch\<business-name>\`. Runs on Opus 4.7,
effort: high.

## How to use

From `CMS - websites`, launch Claude Code (optionally `claude --model claude-opus-4-7 --effort high`),
then:

> "Use the website-builder agent to fetch this design and implement it in a new folder: `<URL>`"

The agent derives the business name from the design's README (or asks), defaults to EN + NL,
and asks one focused question if anything is genuinely ambiguous. See `example-prompts.md` for
more invocations and `phases/GOAL_TEMPLATE.md` for `/goal` and `/ralph-loop` presets.

## What it produces

`scratch\<business-name>\` — a Next.js 16 App Router site with `app/[locale]/` routing,
`components/sections/`, next-intl i18n, `messages/{en,nl}.json`, SEO (sitemap/robots/JSON-LD/OG/
hreflang), Motion animations, Playwright E2E, a `.learnings/` log, `BUILD_PLAN.md`, and
`_design-manifest.json`. `output: 'standalone'` for Hetzner Docker.

## Files

- `AGENTS.md` — authoritative spec (constants, 8 phases, aesthetic fallback)
- `LEARNINGS.md` — append-only cross-build meta-lessons
- `example-prompts.md` — invocation examples
- `phases/N-*.md` — thin per-phase orchestration (lazy-loaded by the subagent)
- `phases/GOAL_TEMPLATE.md` — `/goal` and `/ralph-loop` presets
- `learnings-template/` — seeded into each generated site's `.learnings/`
- `.claude/agents/website-builder.md` — the executable subagent
- `.claude/skills/{design-handoff,nextjs-app-scaffolding,i18n-setup,seo-pro,responsive-audit,motion-animations,playwright-user-stories}/` — bundled skills

## Defaults

shadcn/ui · Motion (`motion/react`) · next-intl · EN+NL · locale prefix `always` · placeholders
(no auto-translation) · mock images kept as-is · sibling output folder · escalate after 3 retries.

## Cost note

Opus 4.7 + effort: high is maximum-quality, maximum-cost. A typical 3–5 page multilingual build
runs ~$5–20 on Pro/Max plans. Overnight `/ralph-loop` runs cost more — set `--max-iterations` and
monitor. To dial back, change the subagent frontmatter to `model: claude-sonnet-4-6` /
`effort: medium`, or launch with those flags.
```

- [ ] **Step 2: Write `example-prompts.md`** (adapted from the package; root-relative `learnings-template` reference points at the agent folder)

```markdown
# Example prompts — website-builder agent

Launch from `CMS - websites`, optionally with `claude --model claude-opus-4-7 --effort high`.

## Minimal — let the agent decide

```
Use the website-builder agent to fetch this design and implement it in a new folder:
<Claude Design URL>
```

## Folder-name hint

```
Use the website-builder agent. Fetch <URL> and call the output folder "northwind-coffee".
```

## Explicit locales

```
Use the website-builder agent. Fetch <URL>. Locales: en (default), nl, fr. Output folder: acme-corp.
```

```
Use the website-builder agent. Fetch <URL>. English-only — single locale, no switcher.
(The agent still uses the [locale] route structure for future-proofing.)
```

## Structure hint

```
Use the website-builder agent. Build the site from <URL or local path>.
Make it 5 pages: /, /about, /services, /case-studies, /contact. Locales: en + nl.
Primary CTA points to /contact. Serif display font, sans body, restrained animations.
```

## Local folder source

```
Use the website-builder agent. The design is at C:\Users\stefa\Downloads\acme-design-export\.
Output folder: "acme-corp". Locales: en + nl + de. Read the README and implement everything.
```

## After kickoff — /goal (interactive)

See `phases/GOAL_TEMPLATE.md` for the full Preset 1/2/3 condition strings. Paste a `/goal <conditions>`
once the agent has scaffolded.

## Overnight batch — /ralph-loop

See `phases/GOAL_TEMPLATE.md`. Always set `--max-iterations`.

## Permanent rule that should stick

```
Permanent rule for all future builds: never use Inter for the body font; default to "Geist Sans".
Append to .learnings/conventions.md in this project AND to
agents/Website Builder/learnings-template/conventions.md so future builds inherit it.
```

## Inspecting what the agent did

```
Read BUILD_PLAN.md and tell me which items were checked off, then summarize the project's
.learnings/corrections.md and .learnings/conventions.md.
```

```
List every translation key in messages/en.json that's still [NL] in messages/nl.json.
Output as a markdown table for my translation pipeline.
```
```

---

## Task 6: Scaffold `LEARNINGS.md` (empty)

**Files:**
- Create: `agents/Website Builder/LEARNINGS.md`

- [ ] **Step 1: Write the empty scaffold**

```markdown
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
```

---

## Task 7: Add the catalog row to `agents/README.md`

**Files:**
- Modify: `agents/README.md` (the markdown table under "Catalog")

- [ ] **Step 1: Read the current table**

Run: Read `agents/README.md` lines 1-12 to confirm the exact table format and column order
(`Agent | Folder | Skill | Purpose`).

- [ ] **Step 2: Append the new row immediately after the existing `Solver — Issues` row**

Old (the Solver row, ending the table body):
```markdown
| **Solver — Issues** | [`Solver - Issues/`](./Solver%20-%20Issues/) | [`.claude/skills/solver-issues/SKILL.md`](../.claude/skills/solver-issues/SKILL.md) | Autonomous code-fixing worker. Triggered by GitHub Actions cron every 15 min. Claims pending CMS issues (priority-ordered), runs Claude Code action against a cloned client repo, commits the fix to `cms-preview`, then routes back into the S1.5 approval flow. |
```

New (Solver row unchanged + appended Website Builder row):
```markdown
| **Solver — Issues** | [`Solver - Issues/`](./Solver%20-%20Issues/) | [`.claude/skills/solver-issues/SKILL.md`](../.claude/skills/solver-issues/SKILL.md) | Autonomous code-fixing worker. Triggered by GitHub Actions cron every 15 min. Claims pending CMS issues (priority-ordered), runs Claude Code action against a cloned client repo, commits the fix to `cms-preview`, then routes back into the S1.5 approval flow. |
| **Website Builder** | [`Website Builder/`](./Website%20Builder/) | [`.claude/agents/website-builder.md`](../.claude/agents/website-builder.md) (subagent) | Turns a Claude Design export (URL or local folder) into a production-ready, multilingual Next.js 16 site in a sibling `scratch\<business-name>\` folder — i18n (next-intl), SEO + hreflang, Motion animations, responsive + a11y audit, Playwright self-tests. Runs as an Opus-4.7 / effort:high subagent. Self-improves via `LEARNINGS.md` + per-build `.learnings/`. |
```

Note: this agent's entry point is a **subagent** (`.claude/agents/`), not a skill (`.claude/skills/`) — the Skill column points at the subagent file accordingly.

- [ ] **Step 3: Verify the row was added**

Run:
```powershell
Select-String -Path "$repo\agents\README.md" -Pattern "Website Builder"
```
Expected: at least one hit in the table row.

---

## Task 8: Final verification against spec success criteria

**Files:** none (read-only checks)

- [ ] **Step 1: Subagent frontmatter (criterion 1)**

Run:
```powershell
Get-Content "$repo\.claude\agents\website-builder.md" -TotalCount 7
```
Expected: valid frontmatter, `name: website-builder`, `model: claude-opus-4-7`, `effort: high`, `tools:` present.

- [ ] **Step 2: All 7 skills present with matching names (criterion 2)**

Run:
```powershell
foreach ($s in @("design-handoff","nextjs-app-scaffolding","i18n-setup","seo-pro","responsive-audit","motion-animations","playwright-user-stories")) {
  $f = "$repo\.claude\skills\$s\SKILL.md"
  $nameLine = (Select-String -Path $f -Pattern "^name:\s*$s\s*$").Count
  "$s : exists=$(Test-Path $f) nameMatches=$nameLine"
}
```
Expected: each line `exists=True nameMatches=1`.

- [ ] **Step 3: Agent folder contents (criterion 3)**

Run:
```powershell
Get-ChildItem "$repo\agents\Website Builder" -Recurse -Name | Sort-Object
```
Expected: `AGENTS.md`, `README.md`, `LEARNINGS.md`, `example-prompts.md`, `phases/` (8 phase files + GOAL_TEMPLATE.md), `learnings-template/` (conventions.md, corrections.md, failure-modes.md).

- [ ] **Step 4: No stale repo-root learnings-template references (criterion 7)**

Run:
```powershell
Select-String -Path "$repo\.claude\agents\website-builder.md","$repo\.claude\skills\nextjs-app-scaffolding\SKILL.md","$repo\agents\Website Builder\AGENTS.md","$repo\agents\Website Builder\example-prompts.md" -Pattern "learnings-template" | Select-Object Filename, Line
```
Expected: every hit is either a bare `learnings-template/` inside the agent-folder context or the explicit `agents/Website Builder/learnings-template/` path. NONE should imply repo root. NOTE: the package's `nextjs-app-scaffolding` skill has a pitfall bullet "Forgetting to copy `learnings-template/*` into `.learnings/`" — if it implies a root-relative path ambiguously, edit that one bullet to read `agents/Website Builder/learnings-template/*`. This is the only edit allowed to a copied skill.

- [ ] **Step 5: Cross-reference resolution (criterion 4)**

Run:
```powershell
$refs = @(
  "agents\Website Builder\AGENTS.md",
  "agents\Website Builder\phases\1-ingest.md",
  "agents\Website Builder\phases\8-verify.md",
  "agents\Website Builder\learnings-template\conventions.md"
)
foreach ($r in $refs) { "$r : $(Test-Path (Join-Path $repo $r))" }
```
Expected: all `True`.

- [ ] **Step 6: Report results to the user** — a short table of the 7 spec success criteria with pass/fail, plus the output of any failed check. No commit (Stefan commits explicitly).

---

## Self-Review (completed by plan author)

**Spec coverage:**
- Architecture (repo convention + subagent) → Tasks 2 (subagent), 3 (AGENTS.md), 7 (catalog). ✓
- Anti-drift split → Task 2 (lazy table), Task 4 (thin phases point at skills). ✓
- File layout → Tasks 1–7 create every listed file. ✓
- Path adaptations (learnings-template relocation) → Task 2 subagent + Task 8 Step 4 scaffolding-skill edit. ✓
- 7 skills verbatim → Task 1. ✓
- Two learnings layers → Task 6 (agent LEARNINGS.md) + Task 1 (learnings-template). ✓
- Author-files-only / no MCP mutation / no commit → stated in Task 1 Step 6, Task 8 Step 6. ✓
- All 7 success criteria → Task 8 Steps 1–5 map to criteria 1,2,3,7,4; criteria 5 (no dup) enforced by Task 4 thin-phase design; criterion 6 (catalog row) → Task 7. ✓

**Placeholder scan:** No "TBD"/"TODO"/"similar to" — full content given for every authored file; verbatim files use exact copy commands. ✓

**Type/path consistency:** Folder name "Website Builder" (with space) used consistently; URL-encoded `Website%20Builder` in markdown links; skill folder names match the 7 in every list. ✓
```
