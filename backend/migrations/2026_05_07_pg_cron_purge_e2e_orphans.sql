-- backend/migrations/2026_05_07_pg_cron_purge_e2e_orphans.sql
-- Daily janitor — deletes E2E orphan rows older than 24 h.
--
-- Why this exists even after test-cleanup hardening:
--   The integration suite uses try/finally + asserts on the DELETE
--   response, so happy-path cleanup is reliable. But a runner SIGKILL
--   (GitHub Actions OOM, network drop, maintenance) between `create`
--   and `finally` leaves an orphan row that the dashboard now hides
--   (services/test_data.py filter) but that still occupies storage.
--
-- This pg_cron job runs at 04:00 UTC every day, deleting any
-- throwaway-* row older than 24 h. The 24 h delay is a safety
-- margin — long enough that an E2E run finishing legitimately
-- (max ~10 min wall) is never mid-test when the janitor sweeps.
--
-- Apply via Supabase dashboard → SQL editor (one-time). After this
-- runs successfully, the test-data dashboard pollution problem is
-- self-healing — no operator intervention needed.

-- 1. Enable the extension (idempotent — Supabase ships it pre-installed
--    but disabled).
CREATE EXTENSION IF NOT EXISTS pg_cron;

-- 2. Drop any prior version of the job so this migration is idempotent.
SELECT cron.unschedule('purge-e2e-orphans')
WHERE EXISTS (SELECT 1 FROM cron.job WHERE jobname = 'purge-e2e-orphans');

-- 3. Schedule the daily purge.
SELECT cron.schedule(
  'purge-e2e-orphans',
  '0 4 * * *',
  $$
    DELETE FROM public.users
    WHERE (email LIKE 'throwaway-%@cms-test.dev'
        OR email LIKE 'throwaway-%@cms-test.local')
      AND created_at < now() - interval '24 hours';

    DELETE FROM public.projects
    WHERE slug LIKE 'throwaway-%'
      AND created_at < now() - interval '24 hours';
  $$
);

-- 4. Sanity check — print the scheduled job so the dashboard SQL
--    editor confirms registration.
SELECT jobname, schedule, command FROM cron.job WHERE jobname = 'purge-e2e-orphans';
