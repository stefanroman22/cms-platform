-- backend/migrations/2026_06_04_bookings_manage.sql
-- Client self-service cancel/reschedule: token-secured management links.
alter table public.bookings add column if not exists manage_token text;
alter table public.bookings add column if not exists google_event_id text;
alter table public.bookings add column if not exists reschedule_count int not null default 0;

create unique index if not exists bookings_manage_token_uniq
  on public.bookings (manage_token);
