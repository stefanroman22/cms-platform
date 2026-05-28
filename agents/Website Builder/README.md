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
