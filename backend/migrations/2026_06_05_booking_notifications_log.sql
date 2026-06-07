-- backend/migrations/2026_06_05_booking_notifications_log.sql
-- Additive: creates booking_notifications_log for per-booking, per-offset
-- email idempotency. Apply via Supabase MCP (apply_migration).

create table if not exists public.booking_notifications_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  booking_id uuid references public.bookings(id) on delete cascade,
  type text not null,            -- confirm_customer|confirm_owner|reminder|reschedule|cancel
  offset_min int,                -- for reminders; null otherwise
  channel text not null default 'email',
  status text not null default 'sent',
  idempotency_key text not null unique,
  provider_id text,
  error text,
  created_at timestamptz not null default now(),
  sent_at timestamptz
);

create index if not exists booking_notif_booking
  on public.booking_notifications_log (booking_id);

alter table public.booking_notifications_log enable row level security;
