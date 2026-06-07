-- backend/migrations/2026_06_06_booking_widget_color.sql
-- Decouple the booking widget's accent color from the email accent color.
-- Until now a single booking_settings.accent_color drove BOTH the confirmation
-- emails AND the public booking widget's --color-accent (button / dates / hover
-- effects), so setting a black email accent turned the on-site calendar black
-- too. Add a dedicated widget_color for the widget; accent_color stays email-only.
-- Idempotent: safe to re-run.

alter table public.booking_settings add column if not exists widget_color text;

-- Tenant #1 (Roman Technologies): the widget keeps the signature antique-brass
-- gold (--color-accent #c9a961) while the email accent is independently black.
update public.booking_settings
   set widget_color = '#c9a961', updated_at = now()
 where tenant_id = 'a7fccf9f-35ba-4655-baba-6744cab738dc'
   and widget_color is null;
