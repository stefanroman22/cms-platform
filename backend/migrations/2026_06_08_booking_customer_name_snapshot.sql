-- backend/migrations/2026_06_08_booking_customer_name_snapshot.sql
-- Snapshot the customer's name onto each booking row at creation time.
--
-- Why: booking_customers is keyed by (tenant_id, email) and the name lives on that
-- shared row. Two bookings from one email but different names (e.g. someone booking
-- for two family members) collapse to one customer, and upsert_customer overwrites
-- the name with whoever booked last. Every later display/email of the earlier
-- booking (manage page, owner dashboard, reschedule/cancel/reminder mail) then shows
-- the wrong name. A booking is a point-in-time event, so it should record who it was
-- for when it was made. Idempotent — safe to re-run.

alter table public.bookings add column if not exists customer_name text;

-- Backfill existing rows from their current customer row. (Best effort: rows whose
-- customer was already overwritten keep the latest name, which is no worse than today.)
update public.bookings b
set customer_name = c.name
from public.booking_customers c
where b.customer_id = c.id
  and b.customer_name is null;
