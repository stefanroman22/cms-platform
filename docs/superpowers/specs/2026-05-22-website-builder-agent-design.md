# Website Builder Agent — Design

**Date:** 2026-05-22
**Status:** Approved (structure)
**Source package:** `C:\Users\stefa\Downloads\website-builder-agent`

## Purpose

Bring the downloaded `website-builder-agent` package into this repo as a first-class
agent. It turns a Claude Design export (URL or local folder) into a production-grade,
multilingual Next.js 16 site in a **sibling** folder under
`C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\` — with i18n (next-intl),
SEO, responsiveness, Motion animations, and Playwright self-tests.

## Architecture decision

The package ships as a **Claude Code subagent** (`website-builder.md` with
`model: claude-opus-4-7`, `effort: high`, `tools:` frontmatter) + 7 bundled skills. This
repo's `agents/` folder uses a different convention (per [agents/README.md](../../../agents/README.md)):
each agent owns a folder with `AGENTS.md` + `README.md` + `LEARNINGS.md` + `phases/N.md`,
plus a thin `.claude/` entry point.

**Chosen approach (user-approved): repo convention + real subagent.**
The `agents/Website Builder/` folder is the source-of-truth documentation; the executable
is the real subagent at `.claude/agents/website-builder.md`. This mirrors how Design Prompt
Creator has both a docs folder *and* a `.claude/skills/` entry point, while preserving the
subagent's Opus/effort dispatch isolation.

Rejected alternatives:
- *Faithful package install* (drop files into `.claude/` only) — ignores the `agents/`
  catalog convention and the user's "in the folder agents" instruction.
- *Full skill-pipeline conversion* (no real subagent, main thread runs phases) — loses
  subagent isolation and the package's intended Opus-4.7/effort:high dispatch model.

## Anti-drift principle

Phase logic lives in exactly one place per concern:
- **Frontmatter + hard behavioral rules + lazy phase-loading table** → `.claude/agents/website-builder.md`
- **Authoritative human-readable workflow spec** → `agents/Website Builder/AGENTS.md`
- **Thin per-phase orchestration** ("apply skill X → produce artifact Y → gate Z") → `phases/N.md`
- **Deep "HOW" expertise** → the 7 `.claude/skills/*/SKILL.md` (copied verbatim from package)

`phases/N.md` files NEVER re-explain what a skill already covers — they point at it.

## File layout

```
agents/Website Builder/
├── AGENTS.md                 # authoritative spec: 8 phases, behavioral rules, constants table
├── README.md                 # quick reference: invoke, files, defaults, cost note
├── LEARNINGS.md              # append-only cross-build meta-lessons, scaffolded empty
├── example-prompts.md        # invocation examples (adapted from package)
├── phases/
│   ├── 1-ingest.md           # design-handoff → _design-manifest.json
│   ├── 2-clarify.md          # clarifying-question rules → BUILD_PLAN.md
│   ├── 3-scaffold.md         # nextjs-app-scaffolding + i18n-setup
│   ├── 4-implement.md        # motion-animations + frontend-design/ui-ux-pro-max
│   ├── 5-seo.md              # seo-pro
│   ├── 6-responsive.md       # responsive-audit + a11y
│   ├── 7-self-test.md        # playwright-user-stories
│   ├── 8-verify.md           # npm build + lighthouse + learn
│   └── GOAL_TEMPLATE.md      # /goal & /ralph-loop presets (agent-owned)
└── learnings-template/
    ├── conventions.md        # seeded into each generated site's .learnings/
    ├── corrections.md
    └── failure-modes.md

.claude/agents/
└── website-builder.md        # THE SUBAGENT (executable). Frontmatter + behavioral rules +
                              # lazy phase table pointing at agents/Website Builder/phases/N.md

.claude/skills/               # 7 bundled skills, verbatim (no collision with existing 4)
├── design-handoff/SKILL.md
├── nextjs-app-scaffolding/SKILL.md
├── i18n-setup/SKILL.md
├── seo-pro/SKILL.md
├── responsive-audit/SKILL.md
├── motion-animations/SKILL.md
└── playwright-user-stories/SKILL.md
```

Plus: one catalog row appended to [agents/README.md](../../../agents/README.md).

## Path adaptations from the package

The package puts `learnings-template/`, `GOAL_TEMPLATE.md`, and `example-prompts.md` at repo
root. We relocate all three **inside** `agents/Website Builder/` so the agent owns everything
it needs (repo's "each agent owns its folder" rule). Two references must be updated to point at
`agents/Website Builder/learnings-template/`:
1. The subagent's Phase-3 "Copy `learnings-template/*` into `.learnings/`" instruction.
2. The `nextjs-app-scaffolding` skill's pitfall note about copying the template.

All other package content (the 7 skills, the 8-phase workflow, hard constraints, Stefan-specific
constants like the scratch path and EN+NL default) is preserved verbatim.

## What the subagent does (8 phases, unchanged from package)

1. **Ingest** — `design-handoff` → `_design-manifest.json`
2. **Clarify** — ask one focused question if genuinely ambiguous → `BUILD_PLAN.md`
3. **Scaffold** — `nextjs-app-scaffolding` + `i18n-setup`; copy mock images; seed `.learnings/`
4. **Implement** — per section; `motion-animations` (motion/react) + external `frontend-design`/`ui-ux-pro-max` if present
5. **SEO** — `seo-pro` (metadata, sitemap, robots, JSON-LD, OG, hreflang)
6. **Responsive + a11y** — `responsive-audit` breakpoint sweep + axe-core
7. **Self-test** — `playwright-user-stories` E2E + per-locale smoke
8. **Verify & learn** — `npm run build`, optional Lighthouse, append to `LEARNINGS.md`

## Hard constraints (carried from package, never violated)

- Animation: `motion` via `motion/react` — never `framer-motion`.
- i18n: `next-intl` — never `next-i18next`/`react-i18next`.
- Output is a **sibling** of "CMS - websites", never nested.
- Every page under `app/[locale]/`.
- `next/image` (except inside `next/og`), `next/font`, no `localStorage`/`sessionStorage`.
- Mock images copied as-is; never fetch stock replacements.
- Non-default locales get `[XX]` placeholders; never auto-translate.
- Escalate after 3 retries on the same failing step.

## Scope boundaries

- **Author files only.** No global MCP/config mutation. Playwright MCP is already connected
  in this environment, so no `claude mcp add` is run.
- **No commit** of generated files unless Stefan asks (standing repo rule).
- Verification limited to confirming the subagent frontmatter is well-formed and the
  cross-references resolve. We do not run a full website build as part of installation.

## Success criteria

1. `.claude/agents/website-builder.md` exists with valid frontmatter (`name: website-builder`,
   `model: claude-opus-4-7`, `effort: high`, `tools:` line) starting at line 1.
2. All 7 skills present under `.claude/skills/<name>/SKILL.md`, each skill's `name:` matching its folder.
3. `agents/Website Builder/` contains AGENTS.md, README.md, LEARNINGS.md (empty scaffold),
   example-prompts.md, 8 phase files + GOAL_TEMPLATE.md, and learnings-template/ (3 files).
4. Every cross-reference path in the subagent + phases resolves to a real file.
5. No phase file duplicates skill content; each points at its skill.
6. A catalog row for "Website Builder" exists in `agents/README.md`.
7. `grep` for the old root-relative `learnings-template/` path in the subagent + scaffolding
   skill returns zero stale references (all point at `agents/Website Builder/learnings-template/`).
```
