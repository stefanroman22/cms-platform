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
