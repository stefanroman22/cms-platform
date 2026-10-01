-- backend/migrations/2026_09_30_drop_booking_reminder_cron.sql
-- Removes the paused booking-reminder cron job and its Vault secret.
-- Reminders were never switched on (job created inactive in
-- 2026_06_05_booking_reminders_cron.sql) and no tenant has had a booking, so
-- the shared secret guarded nothing. BOOKING_CRON_SECRET was removed from
-- Vercel `cms-backend-roman` at the same time; with it unset the backend
-- rejects every call to POST /booking/cron/reminders.
--
-- To bring reminders back: set a new BOOKING_CRON_SECRET on Vercel, create the
-- Vault secret with the same value
--   select vault.create_secret('<value>', 'booking_cron_secret');
-- then re-apply 2026_06_05_booking_reminders_cron.sql and follow its steps.

select cron.unschedule('send-booking-reminders')
where exists (select 1 from cron.job where jobname = 'send-booking-reminders');

delete from vault.secrets where name = 'booking_cron_secret';
