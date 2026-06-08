# Website Builder — AGENTS.md (authoritative spec)

This is the source-of-truth spec for the **website-builder** agent. The executable lives at
`.claude/agents/website-builder.md` (a Claude Code subagent, `model: claude-opus-4-8`,
`effort: xhigh`). This file documents the full workflow; per-phase mechanics live in
`phases/N-*.md` and the deep expertise lives in the bundled `.claude/skills/*`.

Guidelines here apply to this agent only — they do not cascade to other agents.

## What it does

Turns a Claude Design export (URL or local folder) into a production-grade, multilingual
Next.js 16 site in a sibling folder under `C:\Users\stefa\.gemini\antigravity\scratch\<business-name>\`.

**Thoroughness:** runs at `xhigh` reasoning effort. Be exhaustive — multi-pass self-review of every phase, verify at all breakpoints, and don't declare a phase done until you've re-checked it. (This is a restricted subagent: it does NOT have the Workflow/Agent tool, so it cannot fan out multi-agent work — depth comes from xhigh effort + disciplined multi-pass rigor.)

## Constants

| Decision | Default |
|---|---|
| Model | `claude-opus-4-8` (subagent frontmatter) |
| Thinking effort | `xhigh` |
| Component library | shadcn/ui (vendored) |
| Animation library | Motion (`motion/react` import) |
| i18n library | next-intl |
| Default locales | EN + NL |
| Locale prefix style | `always` (`/en/about`, `/nl/about`) |
| Translation strategy | Seed files mirror default locale; CMS auto-translates once connected |
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
  `.learnings/conventions.md` AND `agents/Website Builder/learnings-template/conventions.md` so
  future builds inherit it.
