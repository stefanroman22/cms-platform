-- STATUS: APPLIED 2026-09-27 (Supabase MCP apply_migration).
--
-- 2026-09-27: one-off data cleanup (Stefan-approved). Every affected row was exported first
-- to a local backup (C:\Users\stefa\cms-db-backup-2026-09-27). Idempotent: re-running deletes
-- nothing new except fresh stale sessions / rate-limit rows.

begin;

-- All bookings were demo checks: remove them with their customers and audit rows.
-- (booking_notifications_log rows cascade from bookings.)
delete from public.booking_audit_log;
delete from public.bookings;
delete from public.booking_customers;

-- Laurian's site doesn't use booking: remove its whole booking configuration.
delete from public.booking_service_resources where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_policies          where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_exceptions        where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_hours             where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_services          where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_resources         where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');
delete from public.booking_settings          where tenant_id = (select id from public.projects where slug = 'laurian-duma-portfolio');

-- Test junk project requests ("dsds", "sdsdsd", …), all pending since May.
delete from public.project_requests;

-- Unused test accounts (e2e uses @cms-test.dev); one of them was an admin.
delete from public.users where email like '%@cms-test.local';

-- Supabase Auth is not used (ADR-0003); these rows never signed in. No FK or trigger links
-- auth.users to public.users, so this cannot remove real accounts.
delete from auth.users;

-- Admin API keys no workflow uses: the removed Solver agent's key and the old e2e-CI key.
delete from public.admin_api_keys where name in ('solver-agent-cms', 'agent-prod');

-- Dead sessions and stale rate-limit windows (the new gc cron jobs keep them small from now on).
delete from public.sessions where expires_at < now() or revoked;
delete from public.rate_limits where window_start < now() - interval '1 day';

-- akris had an empty locale list; its content is English.
update public.projects set locales = array['en']
where slug = 'akris' and (locales is null or cardinality(locales) = 0);

commit;
