-- backend/migrations/2026_06_05_booking_reminders_cron.sql
-- Schedules the booking reminder job: pg_cron fires POST /booking/cron/reminders
-- every 5 minutes via pg_net, authenticated with the X-Cron-Secret header.
-- Supersedes 2026_06_03_booking_reminders_cron.sql (same job name; idempotent).
--
-- APPLIED 2026-09-25, with the job created INACTIVE (active = false). No secret
-- value is written by this file. The job reads it from Supabase Vault at run time.
--
-- To turn reminders on (human steps, secret values are never committed):
--   1. Vercel project `cms-backend-roman`, Production: BOOKING_CRON_SECRET is set.
--   2. Supabase Vault secret `booking_cron_secret` holds the SAME value
--      (already exists as of 2026-09-25; confirm it matches, or rotate both):
--        select vault.update_secret(
--          (select id from vault.secrets where name = 'booking_cron_secret'),
--          '<same value as BOOKING_CRON_SECRET>');
--   3. Deploy the backend that has the reminder code you want customers to get.
--   4. Activate the job:
--        select cron.alter_job(
--          (select jobid from cron.job where jobname = 'send-booking-reminders'),
--          active := true);
--   5. Check it: select status, return_message, start_time from cron.job_run_details
--        where jobid = (select jobid from cron.job where jobname = 'send-booking-reminders')
--        order by start_time desc limit 5;
--      and select status_code, content from net._http_response order by created desc limit 5;
--      (200 {"sent": N} = working, 403 = secret mismatch)

create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('send-booking-reminders')
where exists (select 1 from cron.job where jobname = 'send-booking-reminders');

select cron.schedule(
  'send-booking-reminders',
  '*/5 * * * *',
  $$
  -- No-op (no request) while the Vault secret is missing, instead of POSTing a
  -- header-less request that the backend 403s every 5 minutes.
  select net.http_post(
    url := 'https://cms-backend-roman.vercel.app/booking/cron/reminders',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Cron-Secret', s.decrypted_secret
    )
  )
  from vault.decrypted_secrets s
  where s.name = 'booking_cron_secret' and s.decrypted_secret is not null;
  $$
);

-- Created paused: see step 4 above.
select cron.alter_job(
  (select jobid from cron.job where jobname = 'send-booking-reminders'),
  active := false
);

select jobname, schedule, active from cron.job where jobname = 'send-booking-reminders';
