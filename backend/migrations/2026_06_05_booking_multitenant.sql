-- backend/migrations/2026_06_05_booking_multitenant.sql
-- Multi-tenant booking foundation (Phase 1). Evolves public.bookings and adds
-- the booking_* table set, keyed by tenant_id = projects.id. Idempotent/guarded
-- so a re-run is safe. Tenant #1 = the Roman Technologies project.

create extension if not exists btree_gist;
create extension if not exists pgcrypto with schema extensions;

-- ---------- satellite tables ----------
create table if not exists public.booking_settings (
  tenant_id uuid primary key references public.projects(id) on delete cascade,
  public_slug text unique not null,
  timezone text not null,
  locale text not null default 'en',
  business_name text,
  logo_url text,
  primary_color text,
  accent_color text,
  email_from_name text,
  owner_notification_email text not null,
  meeting_url text,
  slot_granularity_min int not null default 15,
  reminders_enabled boolean not null default true,
  reminder_offsets_min int[] not null default '{1440,120}',
  calendar_provider text not null default 'none' check (calendar_provider in ('none','google')),
  is_active boolean not null default true,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.booking_resources (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  type text not null default 'generic' check (type in ('staff','room','equipment','generic')),
  capacity int not null default 1,
  is_active boolean not null default true,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists booking_resources_tenant on public.booking_resources (tenant_id);

create table if not exists public.booking_services (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  description text,
  color text,
  duration_min int not null,
  buffer_before_min int not null default 0,
  buffer_after_min int not null default 0,
  lead_time_min int not null default 0,
  max_advance_days int not null default 60,
  is_active boolean not null default true,
  sort_order int not null default 0,
  created_at timestamptz not null default now()
);
create index if not exists booking_services_tenant on public.booking_services (tenant_id);

create table if not exists public.booking_service_resources (
  service_id uuid not null references public.booking_services(id) on delete cascade,
  resource_id uuid not null references public.booking_resources(id) on delete cascade,
  tenant_id uuid not null references public.projects(id) on delete cascade,
  primary key (service_id, resource_id)
);

create table if not exists public.booking_hours (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  resource_id uuid references public.booking_resources(id) on delete cascade,
  weekday int not null check (weekday between 0 and 6),  -- 0 = Sunday (Postgres dow)
  start_time time not null,
  end_time time not null,
  created_at timestamptz not null default now()
);
create index if not exists booking_hours_tenant on public.booking_hours (tenant_id);

create table if not exists public.booking_exceptions (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  resource_id uuid references public.booking_resources(id) on delete cascade,
  date date not null,
  is_closed boolean not null default true,
  start_time time,
  end_time time,
  created_at timestamptz not null default now()
);
create index if not exists booking_exceptions_tenant on public.booking_exceptions (tenant_id, date);

create table if not exists public.booking_policies (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  service_id uuid references public.booking_services(id) on delete cascade,
  allow_reschedule boolean not null default true,
  reschedule_window_hours int not null default 24,
  max_reschedules int not null default 2,
  allow_cancel boolean not null default true,
  cancellation_window_hours int not null default 24,
  policy_text text,
  created_at timestamptz not null default now()
);
create unique index if not exists booking_policies_tenant_service
  on public.booking_policies (tenant_id, coalesce(service_id, '00000000-0000-0000-0000-000000000000'::uuid));

create table if not exists public.booking_customers (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  name text not null,
  email text not null,
  phone text,
  locale text,
  timezone text,
  created_at timestamptz not null default now(),
  unique (tenant_id, email)
);

create table if not exists public.booking_audit_log (
  id uuid primary key default gen_random_uuid(),
  tenant_id uuid not null references public.projects(id) on delete cascade,
  booking_id uuid,
  action text not null,
  actor text not null check (actor in ('owner','customer','system')),
  payload jsonb,
  created_at timestamptz not null default now()
);
create index if not exists booking_audit_tenant on public.booking_audit_log (tenant_id, created_at);

-- RLS: enabled, no public policies (service-role only) — matches every other table.
alter table public.booking_settings          enable row level security;
alter table public.booking_resources         enable row level security;
alter table public.booking_services          enable row level security;
alter table public.booking_service_resources enable row level security;
alter table public.booking_hours             enable row level security;
alter table public.booking_exceptions        enable row level security;
alter table public.booking_policies          enable row level security;
alter table public.booking_customers         enable row level security;
alter table public.booking_audit_log         enable row level security;

-- ---------- provision tenant #1 (Roman Technologies) ----------
insert into public.booking_settings (
  tenant_id, public_slug, timezone, locale, business_name,
  owner_notification_email, email_from_name, meeting_url,
  slot_granularity_min, reminders_enabled, reminder_offsets_min, calendar_provider
)
values (
  'a7fccf9f-35ba-4655-baba-6744cab738dc', 'roman-technologies-website',
  'Europe/Berlin', 'en', 'Roman Technologies',
  'stefanromanpers@gmail.com', 'Roman Technologies CMS', '',
  45, true, '{60}', 'none'
)
on conflict (tenant_id) do nothing;

insert into public.booking_resources (id, tenant_id, name, type, sort_order)
values ('11111111-1111-1111-1111-111111111111',
        'a7fccf9f-35ba-4655-baba-6744cab738dc', 'Stefan', 'staff', 0)
on conflict (id) do nothing;

insert into public.booking_services (
  id, tenant_id, name, duration_min, buffer_before_min, buffer_after_min,
  lead_time_min, max_advance_days
)
values ('22222222-2222-2222-2222-222222222222',
        'a7fccf9f-35ba-4655-baba-6744cab738dc', 'Consultation', 45, 0, 0, 120, 120)
on conflict (id) do nothing;

insert into public.booking_service_resources (service_id, resource_id, tenant_id)
values ('22222222-2222-2222-2222-222222222222',
        '11111111-1111-1111-1111-111111111111',
        'a7fccf9f-35ba-4655-baba-6744cab738dc')
on conflict do nothing;

-- Hours from BOOKING_HOURS "1=9-20,2=9-20,3=9-20,4=9-20,5=9-20,6=9-17,7=12-17"
-- mapped ISO weekday -> dow (Mon=1..Sat=6, Sun=7->0). Local to Europe/Berlin.
insert into public.booking_hours (tenant_id, resource_id, weekday, start_time, end_time)
select 'a7fccf9f-35ba-4655-baba-6744cab738dc', null, w, s, e
from (values
  (1, time '09:00', time '20:00'),
  (2, time '09:00', time '20:00'),
  (3, time '09:00', time '20:00'),
  (4, time '09:00', time '20:00'),
  (5, time '09:00', time '20:00'),
  (6, time '09:00', time '17:00'),
  (0, time '12:00', time '17:00')
) as h(w, s, e)
where not exists (
  select 1 from public.booking_hours
  where tenant_id = 'a7fccf9f-35ba-4655-baba-6744cab738dc' and resource_id is null
);

insert into public.booking_policies (
  tenant_id, service_id, reschedule_window_hours, max_reschedules,
  cancellation_window_hours, policy_text
)
select 'a7fccf9f-35ba-4655-baba-6744cab738dc', null, 12, 2, 24,
       'Reschedule up to 12h before; cancel up to 24h before.'
where not exists (
  select 1 from public.booking_policies
  where tenant_id = 'a7fccf9f-35ba-4655-baba-6744cab738dc' and service_id is null
);

-- ---------- evolve public.bookings ----------
alter table public.bookings add column if not exists tenant_id uuid;
alter table public.bookings add column if not exists service_id uuid;
alter table public.bookings add column if not exists resource_id uuid;
alter table public.bookings add column if not exists customer_id uuid;
alter table public.bookings add column if not exists guard_start_utc timestamptz;
alter table public.bookings add column if not exists guard_end_utc timestamptz;
alter table public.bookings add column if not exists party_size int not null default 1;
alter table public.bookings add column if not exists manage_token_hash text;
alter table public.bookings add column if not exists source text not null default 'widget';
alter table public.bookings add column if not exists notes text;
alter table public.bookings add column if not exists cancel_reason text;
alter table public.bookings add column if not exists updated_at timestamptz;
alter table public.bookings add column if not exists cancelled_at timestamptz;

-- ---------- backfill the existing rows into tenant #1 ----------
insert into public.booking_customers (tenant_id, name, email, timezone)
select distinct 'a7fccf9f-35ba-4655-baba-6744cab738dc'::uuid, b.name, b.email, b.visitor_timezone
from public.bookings b
where b.tenant_id is null
on conflict (tenant_id, email) do nothing;

update public.bookings b set
  tenant_id   = 'a7fccf9f-35ba-4655-baba-6744cab738dc',
  service_id  = '22222222-2222-2222-2222-222222222222',
  resource_id = '11111111-1111-1111-1111-111111111111',
  customer_id = c.id,
  guard_start_utc = b.start_utc,
  guard_end_utc   = b.end_utc,
  notes = b.note,
  manage_token_hash = case when b.manage_token is not null
                           then encode(extensions.digest(b.manage_token, 'sha256'), 'hex')
                           else null end,
  source = 'widget'
from public.booking_customers c
where b.tenant_id is null
  and c.tenant_id = 'a7fccf9f-35ba-4655-baba-6744cab738dc'
  and c.email = b.email;

-- ---------- tighten + constraints ----------
alter table public.bookings alter column tenant_id set not null;
alter table public.bookings alter column service_id set not null;
alter table public.bookings alter column resource_id set not null;
alter table public.bookings alter column customer_id set not null;
alter table public.bookings alter column guard_start_utc set not null;
alter table public.bookings alter column guard_end_utc set not null;

alter table public.bookings
  add column if not exists guard_range tstzrange
  generated always as (tstzrange(guard_start_utc, guard_end_utc, '[)')) stored;

do $$ begin
  alter table public.bookings add constraint bookings_status_chk
    check (status in ('pending','confirmed','cancelled','completed','no_show'));
exception when duplicate_object then null; end $$;

alter table public.bookings
  add foreign key (tenant_id)   references public.projects(id) on delete cascade;
alter table public.bookings
  add foreign key (service_id)  references public.booking_services(id);
alter table public.bookings
  add foreign key (resource_id) references public.booking_resources(id);
alter table public.bookings
  add foreign key (customer_id) references public.booking_customers(id);

drop index if exists public.bookings_manage_token_uniq;
create unique index if not exists bookings_manage_token_hash_uniq
  on public.bookings (manage_token_hash) where manage_token_hash is not null;

alter table public.bookings drop column if exists name;
alter table public.bookings drop column if exists email;
alter table public.bookings drop column if exists note;
alter table public.bookings drop column if exists visitor_timezone;
alter table public.bookings drop column if exists manage_token;

drop index if exists public.bookings_confirmed_start_uniq;

do $$ begin
  alter table public.bookings add constraint bookings_no_overlap
    exclude using gist (resource_id with =, guard_range with &&)
    where (status in ('pending','confirmed'));
exception when duplicate_object then null; end $$;
