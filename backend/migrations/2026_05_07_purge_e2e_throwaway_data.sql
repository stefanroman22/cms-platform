-- backend/migrations/2026_05_07_purge_e2e_throwaway_data.sql
-- One-time bulk cleanup of E2E test pollution that accumulated in
-- public.users + public.projects before the new pattern-filter
-- (services/test_data.py) and the test-cleanup hardening landed.
--
-- What this deletes:
--   • projects with slug LIKE 'throwaway-%' or slug = 'e2e-test-project'
--     (FK CASCADE removes their project_services + content_entries)
--   • users with email LIKE 'throwaway-%@cms-test.%' (orphan accounts
--     from the create-client integration test that didn't clean up)
--
-- What this PRESERVES:
--   • The two seed users `e2e-user@cms-test.dev` + `e2e-admin@cms-test.dev`
--     (they're the canonical fixtures; integration suite fails without them).
--   • The seeded `e2e-test-project` is rebuilt by `scripts/seed_e2e.py`
--     after this migration applies, so deleting it here is fine.
--
-- Apply via Supabase dashboard → SQL editor. Idempotent (DELETE WHERE
-- pattern is safe to re-run). Safe to apply on a quiet window — no
-- foreground traffic touches these rows.

BEGIN;

-- 1. Bulk delete throwaway projects (FK cascade handles services).
DELETE FROM public.projects
WHERE slug LIKE 'throwaway-%'
   OR slug = 'e2e-test-project';

-- 2. Bulk delete throwaway clients. Excludes the seed users so the
--    integration suite still runs.
DELETE FROM public.users
WHERE email LIKE 'throwaway-%@cms-test.dev'
   OR email LIKE 'throwaway-%@cms-test.local';

-- 3. Verify counts before commit (psql shows them in output).
SELECT
  (SELECT COUNT(*) FROM public.projects WHERE slug LIKE 'throwaway-%') AS leftover_throwaway_projects,
  (SELECT COUNT(*) FROM public.users    WHERE email LIKE 'throwaway-%@cms-test.dev') AS leftover_throwaway_users;

COMMIT;
