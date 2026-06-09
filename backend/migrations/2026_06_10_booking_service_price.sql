-- Booking services get an editable price (EUR). Shown to the customer at booking
-- time and editable by the owner in the dashboard. Nullable + additive — existing
-- services keep NULL (rendered as "price on request" / omitted) until set.
alter table public.booking_services add column if not exists price numeric(10, 2);
