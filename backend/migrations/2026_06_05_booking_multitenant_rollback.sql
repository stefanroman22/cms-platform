-- Rollback for 2026_06_05_booking_multitenant.sql. Restores the pre-migration
-- bookings shape from the backfilled columns. Run ONLY if Task 11 validation fails.
alter table public.bookings drop constraint if exists bookings_no_overlap;
alter table public.bookings add column if not exists name text;
alter table public.bookings add column if not exists email text;
alter table public.bookings add column if not exists note text;
alter table public.bookings add column if not exists visitor_timezone text;
alter table public.bookings add column if not exists manage_token text;
update public.bookings b set
  name  = c.name,
  email = c.email,
  note  = b.notes,
  visitor_timezone = c.timezone
from public.booking_customers c where c.id = b.customer_id;
-- manage_token cannot be un-hashed; existing links keep working via the new
-- hash path, so rollback leaves manage_token null (links break only if you
-- also revert the application code).
create unique index if not exists bookings_confirmed_start_uniq
  on public.bookings (start_utc) where status = 'confirmed';
drop table if exists public.booking_audit_log, public.booking_customers,
  public.booking_policies, public.booking_exceptions, public.booking_hours,
  public.booking_service_resources, public.booking_services,
  public.booking_resources, public.booking_settings cascade;
