-- Per-staff personal time-blocks (R4).
--
-- A "block" is a confirmed booking on ONE barber's calendar with no customer and
-- no service (source = 'block'): lunch, holiday, or an appointment a barber adds
-- for himself. It participates in the per-resource no-overlap exclusion constraint
-- (resource_id WITH =, guard_range WITH &&), so it correctly removes that barber's
-- availability — while customer/service-bearing bookings are unchanged.
--
-- resource_id stays NOT NULL (a block always targets a specific barber). Only
-- service_id and customer_id are relaxed, guarded by a CHECK so non-block rows
-- still require both.
--
-- Behavior-preserving: every existing row has service_id + customer_id and a
-- non-'block' source ('widget' | 'dashboard' | 'api'), so the new CHECK holds for
-- all current rows. Safe to apply ahead of the code deploy: the live backend never
-- inserts blocks, so the relaxed NOT NULLs change nothing until the new code ships.

alter table public.bookings alter column service_id drop not null;
alter table public.bookings alter column customer_id drop not null;

do $$ begin
  alter table public.bookings add constraint bookings_block_or_full_chk
    check (source = 'block' or (service_id is not null and customer_id is not null));
exception when duplicate_object then null; end $$;
