# Website Builder — quick reference

Claude Code subagent that turns a Claude Design export into a production-ready, multilingual
Vite + React 19 SPA (SSG-prerendered) in a sibling folder under `scratch\<business-name>\`. Runs on Opus 4.8,
effort: xhigh.

## How to use

From `CMS - websites`, launch Claude Code (optionally `claude --model claude-opus-4-8 --effort xhigh`),
then:

> "Use the website-builder agent to fetch this design and implement it in a new folder: `<URL>`"

The agent derives the business name from the design's README (or asks), defaults to EN + NL,
and asks one focused question if anything is genuinely ambiguous. See `example-prompts.md` for
more invocations and `phases/GOAL_TEMPLATE.md` for `/goal` and `/ralph-loop` presets.

## What it produces

`scratch\<business-name>\` — a Vite + React 19 SPA pre-rendered by vite-react-ssg, with
React Router v7 locale-prefixed routes, `src/pages/` + `src/routes.tsx`, react-i18next i18n,
`messages/{en,nl}.json`, SEO (prebuild sitemap/robots/OG + React 19 hoisted head + JSON-LD/
hreflang), Motion animations, Playwright E2E, a `.learnings/` log, `BUILD_PLAN.md`, and
`_design-manifest.json`. Static `dist/` output (Vercel static or nginx Docker).

## Files

- `AGENTS.md` — authoritative spec (constants, 8 phases, aesthetic fallback)
- `LEARNINGS.md` — append-only cross-build meta-lessons
- `example-prompts.md` — invocation examples
- `phases/N-*.md` — thin per-phase orchestration (lazy-loaded by the subagent)
- `phases/GOAL_TEMPLATE.md` — `/goal` and `/ralph-loop` presets
- `learnings-template/` — seeded into each generated site's `.learnings/`
- `.claude/agents/website-builder.md` — the executable subagent
- `.claude/skills/{design-handoff,vite-react-scaffolding,i18n-setup,seo-pro,responsive-audit,motion-animations,playwright-user-stories}/` — bundled skills

## Defaults

shadcn/ui · Motion (`motion/react`) · react-i18next · Vite 7 + React 19 · vite-react-ssg · React Router v7 · TanStack Query (localStorage) · Zustand (persist) · EN+NL · locale prefix `always` · seed files mirror default locale (CMS auto-translates once connected) · mock images kept as-is · sibling output folder · escalate after 3 retries.

## Cost note

Opus 4.8 + effort: xhigh is xhigh-effort, maximum-cost. A typical 3–5 page multilingual build
runs ~$5–20 on Pro/Max plans. Overnight `/ralph-loop` runs cost more — set `--max-iterations` and
monitor. To dial back, change the subagent frontmatter to `model: claude-sonnet-4-6` /
`effort: medium`, or launch with those flags.
