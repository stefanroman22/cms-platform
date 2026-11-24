-- 2026-11-24 pg_stat_statements: monthly reset, to cut Disk IO.
-- STATUS: APPLIED 2026-11-24
--
-- Why: Supabase's own metrics exporter (postgres_exporter) reads pg_stat_statements once a
-- minute. Reading it materialises every tracked statement; once the view held ~2,300
-- statements (2.1 MB of query text) that no longer fit in work_mem (2 MB), so every read
-- spilled a ~3 MB temp file to disk: pg_stat_database showed 295,827 temp files / 655 GB
-- since 2026-02-12, against 0.3 GB of WAL from the application. After a manual
-- pg_stat_statements_reset() on 2026-11-24 the exporter's reads stopped creating temp files.
--
-- The view refills slowly (it took about five months to reach the spill size), so a monthly
-- reset keeps it small for good. Cost: the Supabase "Query Performance" page and
-- pg_stat_statements only cover the current month.
--
-- Safe to apply at any time. cron.schedule upserts by job name.
-- Undo: select cron.unschedule('reset-pg-stat-statements');

select cron.schedule(
  'reset-pg-stat-statements', '47 3 1 * *',
  $$select extensions.pg_stat_statements_reset()$$
);
