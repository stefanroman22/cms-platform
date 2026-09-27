-- STATUS: NOT APPLIED (tables still present, checked 2026-09-25). Update this line when applied.
--
-- 2026-08-26: drop DB objects orphaned by the feature removals of this date:
--   * auto-fix / Solver Agent + Slack integration (project_issues,
--     slack_processed_events, the two claim RPCs)
--   * lead scraper (scrape_jobs + leads.scrape_job_id FK, enum, trigger fn)
--   * lead_suppressions (tombstone table whose only reader was the scraper)
--
-- APPLY MANUALLY (Supabase SQL editor or re-authed Supabase MCP). The backend
-- no longer references any of these objects, so applying is safe at any time
-- after the 2026-08-26 code cleanup is deployed. Idempotent.

-- auto-fix / Slack
drop function if exists public.claim_next_solver_issue(int, int);
drop function if exists public.claim_specific_solver_issue(uuid, integer, integer);
drop table if exists public.project_issues cascade;
drop table if exists public.slack_processed_events;

-- scraper
alter table if exists public.leads drop column if exists scrape_job_id;
drop table if exists public.scrape_jobs cascade;
drop function if exists public.scrape_jobs_set_updated_at();
drop type if exists public.scrape_job_status;

-- deleted-lead tombstones (reader was the scraper; writer removed 2026-08-26)
drop table if exists public.lead_suppressions;
