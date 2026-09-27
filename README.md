# Roman Technologies CMS

Headless CMS for small-business client websites: a FastAPI backend (`backend/`, Vercel
`cms-backend-roman`), a Next.js 16 app (`frontend/`: marketing site, client dashboard and
booking widget at roman-technologies.dev), Supabase, and Claude Code agents (`agents/`) that
build client sites and wire them to the CMS.

The source is public for transparency; see [`LICENSE`](./LICENSE) (all rights reserved). It is
not open for contributions: pull requests are closed without review, issues are welcome. Report
security problems privately as described in [`.github/SECURITY.md`](./.github/SECURITY.md).

## Where things are documented

- [`CLAUDE.md`](./CLAUDE.md): commands, safety rules and conventions (written for agents, useful
  for humans).
- [`docs/decisions/`](./docs/decisions/): architectural decisions (ADRs).
- [`security/`](./security/): the findings tracker kept by the weekly review routines, plus the
  [runbook](./security/RUNBOOK.md) (rotation log, incident response).
- Each agent's `agents/<name>/AGENTS.md`.

## Run it locally

See [`RUN.md`](./RUN.md). Note that local servers use the **production** Supabase database, and
production changes only through the manual **Promote dev → main** GitHub Action.
