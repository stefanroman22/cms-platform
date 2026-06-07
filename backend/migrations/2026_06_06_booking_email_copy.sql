-- Additive: per-tenant email copy overrides (key -> custom text). Defaults live
-- in booking_i18n; only overridden keys are stored here.
alter table public.booking_settings
  add column if not exists email_copy jsonb not null default '{}'::jsonb;
