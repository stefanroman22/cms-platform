# Agents

Catalog of all agents in this repo. Each agent owns its own folder with its own `AGENTS.md` spec — guidelines do **not** cascade between agents.

| Agent | Folder | Skill | Purpose |
|-------|--------|-------|---------|
| **CMS Connector — Website** | [`CMS Connector - Website/`](./CMS%20Connector%20-%20Website/) | [`.claude/skills/cms-connector-website/SKILL.md`](../.claude/skills/cms-connector-website/SKILL.md) | Import a client website to GitHub, scan it for editable content, generate a markdown integration report for human review, provision CMS services + Vercel preview, run a test matrix. Self-improves via `LEARNINGS.md`. |

## Adding a new agent

1. Create `agents/<Agent Display Name>/`.
2. Add `AGENTS.md` (workflow spec, scoped to this agent only).
3. Add `LEARNINGS.md` (append-only feedback log, scaffolded empty).
4. Add `phases/<N>-<name>.md` per workflow phase.
5. Add a Claude Code skill: `.claude/skills/<slug>/SKILL.md` with trigger, lazy phase loading, token-optimization rules.
6. Add a row to the table above.

## Conventions

- Folder names may have spaces / hyphens. Python packages cannot — drop `__init__.py`, set `pythonpath = .` in `pytest.ini`, use flat imports.
- Each agent's `AGENTS.md` is authoritative for that agent only. Cross-agent rules go in this README or in a global `CLAUDE.md`.
- Each agent's SKILL.md is the entry point for Claude Code. Keep skill bodies thin — push detail into per-phase files loaded lazily.
- Token-optimization rules live in each agent's SKILL.md (binding) and per-phase `phases/N.md` (`Token tactics` section).
