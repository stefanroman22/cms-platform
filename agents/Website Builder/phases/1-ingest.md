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
