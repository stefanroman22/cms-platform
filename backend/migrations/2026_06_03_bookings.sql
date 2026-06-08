-- backend/migrations/2026_06_03_bookings.sql
-- Custom booking widget — stores appointments made through the marketing site.
create table if not exists public.bookings (
  id uuid primary key default gen_random_uuid(),
  start_utc timestamptz not null,
  end_utc timestamptz not null,
  name text not null,
  email text not null,
  note text,
  visitor_timezone text,
  status text not null default 'confirmed',
  reminder_sent_at timestamptz,
  created_at timestamptz not null default now()
);

-- Race-safe double-book guard: only one confirmed booking per start.
create unique index if not exists bookings_confirmed_start_uniq
  on public.bookings (start_utc)
  where status = 'confirmed';

-- Reminder scan index.
create index if not exists bookings_reminder_scan
  on public.bookings (start_utc)
  where status = 'confirmed' and reminder_sent_at is null;

-- Service-role only (backend). No public policies.
alter table public.bookings enable row level security;
