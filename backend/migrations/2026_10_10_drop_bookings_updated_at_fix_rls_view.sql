-- backend/migrations/2026_10_10_drop_bookings_updated_at_fix_rls_view.sql
-- 1. bookings.updated_at: no trigger sets it and no code (dev or main) reads or
--    writes it — booking_admin_repo's updated_at write targets booking_settings.
-- 2. tenant_rls_status: drop `project_issues` (table dropped 2026_08_26) from the
--    watched list. CREATE OR REPLACE keeps the existing grants (service_role only).

alter table public.bookings drop column if exists updated_at;

create or replace view public.tenant_rls_status
  with (security_invoker = true) as
  select tablename, rowsecurity
  from pg_tables
  where schemaname = 'public'
    and tablename = any (array['users', 'sessions', 'projects', 'content_entries', 'project_requests']::name[]);
