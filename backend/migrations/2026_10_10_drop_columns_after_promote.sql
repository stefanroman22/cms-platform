-- backend/migrations/2026_10_10_drop_columns_after_promote.sql
-- Applied 2026-10-10, after the cleanup was promoted to main. It had to wait:
-- the previous main still selected these columns, so dropping them first would
-- have 500'd every project endpoint (repo_branch), the booking widget
-- (calendar_provider) and admin API-key auth (scopes).
--
--   projects.repo_branch               — nothing reads it; cms-preview is the convention.
--   booking_settings.calendar_provider — Google Calendar sync removed (was "none" everywhere).
--   bookings.google_event_id           — same; never set.
--   admin_api_keys.scopes              — selected but never enforced.
--   leads.ai_score, leads.ai_scored_at — AI scoring was never built; never written.

alter table public.projects drop column if exists repo_branch;
alter table public.booking_settings drop column if exists calendar_provider;
alter table public.bookings drop column if exists google_event_id;
alter table public.admin_api_keys drop column if exists scopes;
alter table public.leads drop column if exists ai_score;
alter table public.leads drop column if exists ai_scored_at;
