# ADR-0001: One Supabase database for every environment

Status: Accepted
Date: 2026-09-27

## Context

The platform is run by one operator for a small number of client sites. Local development, the
Vercel `dev` preview deployments and production all need realistic data: client projects, content,
bookings and leads. A second database would need its own seed data, its own secrets on every
Vercel project, and a way to keep its schema in sync. There is no staff to maintain that.

## Decision

- Local, preview and production all use the single Supabase project `xeluydwpgiddbamysgyu`
  (Postgres, Storage bucket `cms-files`, `pg_cron`). There is no dev or staging database.
- Schema changes are plain SQL files in `backend/migrations/YYYY_MM_DD_<name>.sql`. Nothing
  applies them automatically: an operator applies each one by hand (Supabase MCP
  `apply_migration`, the SQL editor, or `scripts/apply_supabase_migration.py`).
- The migration folder is a ledger. Once a file is applied it is never edited; a fix is a new file.
- A migration that code depends on is applied before, or together with, promoting that code.

Evidence: `CLAUDE.md` (Run), `scripts/apply_supabase_migration.py`,
`backend/auth_service/core/config.py` (`SUPABASE_URL` is the same in every tier).

## Consequences

- One set of data and credentials to manage; local and preview behave exactly like production.
- **Every write is a production write.** Running the backend locally, using a preview deployment,
  running a script or applying a migration changes live client data. There is no rehearsal
  environment.
- Code and schema can drift: code that selects a column that has not been applied yet makes every
  endpoint that uses it return 500. A migration's header comment records whether it is
  applied (`STATUS: NOT APPLIED` / `APPLIED <date>`).
- Backend unit tests must never reach the database; `tests/conftest.py` points them at a dead
  address.
- Do NOT: add a migration runner that applies files on deploy or on startup, edit an applied
  migration, point tests or scripts at the real database casually, or introduce a second database
  without a new ADR that supersedes this one.
