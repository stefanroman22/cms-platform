-- STATUS: APPLIED 2026-09-27 (Supabase MCP apply_migration).
--
-- 2026-09-27: schema cleanup after the SEO/GEO teardown, plus housekeeping jobs.
--   * The SEO/GEO agent, its backend (routers/seo.py) and dashboard tabs were removed on
--     2026-09-27; nothing reads the seo_* tables or the projects.seo_* columns any more.
--   * email_configs was never used by any code (email settings live in content_entries).
--   * rate_limits and sessions were never garbage-collected; cron.job_run_details grows forever.
-- Row data of every dropped table was exported first (local backup, 2026-09-27).

-- ── Drop the SEO/GEO schema ──────────────────────────────────────────────────
drop table if exists public.seo_changes cascade;
drop table if exists public.seo_plan_items cascade;
drop table if exists public.seo_audits cascade;
drop table if exists public.seo_competitors cascade;
drop table if exists public.seo_articles cascade;
drop table if exists public.seo_page_meta cascade;
drop table if exists public.seo_jobs cascade;
drop table if exists public.seo_learnings cascade;
drop table if exists public.seo_runs cascade;

alter table if exists public.projects drop column if exists seo_enabled;
alter table if exists public.projects drop column if exists seo_blog_route;
alter table if exists public.projects drop column if exists seo_last_run_at;

-- ── Drop the never-used email_configs table ──────────────────────────────────
drop table if exists public.email_configs;

-- ── Housekeeping cron jobs (cron.schedule upserts by job name) ───────────────
select cron.schedule(
  'gc-rate-limits', '17 3 * * *',
  $$select public.rate_limit_gc(86400)$$
);

select cron.schedule(
  'gc-sessions', '27 3 * * *',
  $$delete from public.sessions
    where expires_at < now() - interval '7 days'
       or (revoked and created_at < now() - interval '7 days')$$
);

select cron.schedule(
  'gc-cron-history', '37 3 * * 0',
  $$delete from cron.job_run_details where end_time < now() - interval '30 days'$$
);
