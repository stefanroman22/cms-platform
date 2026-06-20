-- Standardize the default reminder offsets to 24h + 1h.
--
-- The previous default was {1440,120} (24h + 2h), but the reminder email copy
-- says "in about an hour", and the product spec is 24h + 1h. Align the column
-- default for future tenants, and migrate existing rows that still carry the old
-- default (custom-set values are preserved).
--
-- Idempotent.

alter table public.booking_settings
  alter column reminder_offsets_min set default '{1440,60}';

update public.booking_settings
   set reminder_offsets_min = '{1440,60}'
 where reminder_offsets_min = '{1440,120}';
