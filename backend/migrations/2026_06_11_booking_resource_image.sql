-- Staff avatar for booking resources.
--
-- Adds an optional public-facing image URL to each booking resource (staff
-- member). Shown next to the staff name in the owner's calendar and on the
-- customer-facing booking flow. Empty/null => the UI renders a default
-- placeholder avatar, so an image is never required.
--
-- Idempotent + behaviour-preserving: existing rows get NULL (rendered as the
-- default avatar). No backfill needed.

alter table public.booking_resources
  add column if not exists image_url text;
