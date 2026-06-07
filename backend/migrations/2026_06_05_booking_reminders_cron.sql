-- backend/migrations/2026_06_05_booking_reminders_cron.sql
-- Apply at deploy time only — the cron target endpoint must be live first.
--
-- Updates the pg_cron job to fire every 5 minutes (unchanged from Phase 1).
-- This file supersedes 2026_06_03_booking_reminders_cron.sql; both schedule
-- the same job name so re-running this is idempotent.
--
-- Runbook:
--   1. Ensure BOOKING_CRON_SECRET is set on the backend (Vercel + backend/.env).
--   2. In the Supabase SQL editor (value NOT committed):
--        select vault.create_secret('<same value as BOOKING_CRON_SECRET>', 'booking_cron_secret');
--   3. Apply this migration AFTER deploying the P4 backend.

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('send-booking-reminders')
where exists (select 1 from cron.job where jobname = 'send-booking-reminders');

select cron.schedule(
  'send-booking-reminders',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://cms-backend-roman.vercel.app/booking/cron/reminders',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Cron-Secret', (select decrypted_secret from vault.decrypted_secrets where name = 'booking_cron_secret')
    )
  );
  $$
);

select jobname, schedule from cron.job where jobname = 'send-booking-reminders';
