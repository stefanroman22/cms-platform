# Multi-Tenant Booking Foundation (Phase 1) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Evolve the existing single-tenant FastAPI booking widget into a reusable, multi-tenant booking foundation (data model + multi-resource slot engine + tenant-scoped public API), with the live "book a call" widget migrated onto it as tenant #1 and still working with zero frontend changes.

**Architecture:** A new `booking_*` table set (FK `tenant_id → projects.id`) plus an evolved `bookings` table guarded by a `btree_gist` exclusion constraint. A thin domain layer (`booking_tenant`, `booking_repo`, evolved `booking_availability`, `calendar_provider`) keeps the router slim and unit-testable. Public booking flows through new **slug-scoped** FastAPI routes; the existing legacy routes are kept as backward-compatible shims bound to tenant #1 so the live frontend is untouched. Authorization is enforced in FastAPI with the service-role Supabase client (the repo's existing pattern); RLS stays enabled-with-no-policies on every booking table.

**Tech Stack:** FastAPI (Python 3.13), Supabase Postgres (`btree_gist`, `pgcrypto`, generated columns, exclusion constraints), supabase-py service-role client, `zoneinfo` for DST, Resend-over-urllib emails, pytest + FastAPI `TestClient`. Migrations are `YYYY_MM_DD_*.sql` in `backend/migrations/`, applied via the Supabase MCP.

---

## Spec

This plan implements `docs/superpowers/specs/2026-06-05-multi-tenant-booking-foundation-design.md`. Read it before starting.

## Implementation refinements vs. the spec (deliberate, read first)

These refine spec implementation details without changing its intent:

1. **No frontend changes in Phase 1.** Instead of repointing the live widget at tenant #1's slug (spec §10), the legacy routes (`GET /booking/availability`, `GET /booking/slots`, `POST /booking`, `GET|POST /booking/manage/{token}…`) are kept as **shims bound to tenant #1**. The slug-based frontend cutover moves to Phase 3 (the embeddable widget). End state is identical; the live widget carries zero risk during P1.
2. **`guard_range` is backed by two plain columns.** `bookings` gets `guard_start_utc timestamptz` + `guard_end_utc timestamptz` and a **generated** `guard_range tstzrange generated always as (tstzrange(guard_start_utc, guard_end_utc, '[)')) stored`. The exclusion constraint uses the generated range; the slot engine reads the two plain timestamptz columns (no PostgREST range-string parsing). Same semantics as spec §5.9, friendlier access.
3. **`booking_settings.meeting_url`** is added (nullable) to preserve tenant #1's email "Join the call" link behavior; in-person tenants leave it null.
4. **Emails are functionally multi-tenant but single-brand in P1.** Recipients, times, and the host address come from the resolved tenant; the *visual* branding (Roman Technologies header/logo, "Stefan" copy) stays hardcoded until P4. Safe because no client widget is live until P3 and per-tenant email branding lands in P4.

## Module map

| File | Responsibility | New/Modify |
|---|---|---|
| `backend/migrations/2026_06_05_booking_multitenant.sql` | Schema + ALTER + tenant-#1 provisioning + 7-row backfill + exclusion | Create |
| `backend/auth_service/core/config.py` | Add `BOOKING_MANAGE_BASE_URL` | Modify |
| `backend/auth_service/services/booking_tenant.py` | Resolve a tenant's config (settings + slug) | Create |
| `backend/auth_service/services/booking_availability.py` | Pure multi-resource, DST-aware slot math | Modify (rewrite) |
| `backend/auth_service/services/booking_repo.py` | All booking DB I/O (services, resources, hours, exceptions, guard ranges, customer upsert, booking insert/update, token lookup, audit) | Create |
| `backend/auth_service/services/calendar_provider.py` | `CalendarProvider` protocol + Noop + Google adapter + `provider_for` | Create |
| `backend/auth_service/services/booking_email.py` | Parametrize host recipient | Modify |
| `backend/auth_service/services/booking_manage_email.py` | Parametrize host recipient | Modify |
| `backend/auth_service/routers/booking.py` | Slug-scoped routes + legacy shims + token hashing + audit | Modify (rewrite) |
| `backend/auth_service/tests/test_booking_*` | Extend / add | Modify + Create |

---

# PART A — Schema & domain layer

## Task 1: Migration — schema, provisioning, backfill, exclusion

**Files:**
- Create: `backend/migrations/2026_06_05_booking_multitenant.sql`

This task writes the SQL only. It is **applied** in Task 11 (after the domain + API are built and unit-tested), to keep the live DB on the working schema until cutover. Tenant #1 = project `roman-technologies-website` (`a7fccf9f-35ba-4655-baba-6744cab738dc`).

- [ ] **Step 1: Write the migration file**

```sql
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
```

- [ ] **Step 2: Write the matching rollback file (for Task 11 safety)**

Create `backend/migrations/2026_06_05_booking_multitenant_rollback.sql`:

```sql
-- Rollback for 2026_06_05_booking_multitenant.sql. Restores the pre-migration
-- bookings shape from the backfilled columns. Run ONLY if Task 11 validation fails.
alter table public.bookings drop constraint if exists bookings_no_overlap;
alter table public.bookings add column if not exists name text;
alter table public.bookings add column if not exists email text;
alter table public.bookings add column if not exists note text;
alter table public.bookings add column if not exists visitor_timezone text;
alter table public.bookings add column if not exists manage_token text;
update public.bookings b set
  name  = c.name,
  email = c.email,
  note  = b.notes,
  visitor_timezone = c.timezone
from public.booking_customers c where c.id = b.customer_id;
-- manage_token cannot be un-hashed; existing links keep working via the new
-- hash path, so rollback leaves manage_token null (links break only if you
-- also revert the application code).
create unique index if not exists bookings_confirmed_start_uniq
  on public.bookings (start_utc) where status = 'confirmed';
drop table if exists public.booking_audit_log, public.booking_customers,
  public.booking_policies, public.booking_exceptions, public.booking_hours,
  public.booking_service_resources, public.booking_services,
  public.booking_resources, public.booking_settings cascade;
```

- [ ] **Step 3: Commit**

```bash
git add backend/migrations/2026_06_05_booking_multitenant.sql backend/migrations/2026_06_05_booking_multitenant_rollback.sql
git commit -m "feat(booking): add multi-tenant migration (schema + backfill, not yet applied)"
```

---

## Task 2: Config — manage-link base URL

**Files:**
- Modify: `backend/auth_service/core/config.py:54-56`

- [ ] **Step 1: Add the setting**

After the `BOOKING_MAX_RESCHEDULES` line (config.py:56), add:

```python
    # Base URL for building /manage/{token} links (defaults to the public base).
    BOOKING_MANAGE_BASE_URL: str = ""
```

And add a property near `booking_working_days` (after config.py:96):

```python
    @property
    def manage_base_url(self) -> str:
        return self.BOOKING_MANAGE_BASE_URL or self.BOOKING_PUBLIC_BASE_URL
```

- [ ] **Step 2: Verify import works**

Run: `cd backend && python -c "from auth_service.core.config import settings; print(settings.manage_base_url)"`
Expected: prints `https://roman-technologies.dev` (the default).

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/core/config.py
git commit -m "feat(booking): add BOOKING_MANAGE_BASE_URL setting"
```

---

## Task 3: `booking_tenant.py` — tenant config resolution

**Files:**
- Create: `backend/auth_service/services/booking_tenant.py`
- Test: `backend/auth_service/tests/test_booking_tenant.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_tenant.py
from unittest.mock import MagicMock, patch

from auth_service.services import booking_tenant


def _sb_returning(rows):
    sb = MagicMock()
    for m in ["table", "select", "eq", "limit"]:
        getattr(sb, m).return_value = sb
    sb.execute.return_value = type("R", (), {"data": rows})()
    return sb


SETTINGS_ROW = {
    "tenant_id": "t1", "public_slug": "acme", "timezone": "Europe/Berlin",
    "locale": "en", "business_name": "Acme", "owner_notification_email": "o@acme.com",
    "email_from_name": "Acme", "meeting_url": "", "slot_granularity_min": 15,
    "reminders_enabled": True, "reminder_offsets_min": [60], "calendar_provider": "none",
    "is_active": True,
}


def test_load_by_slug_returns_config():
    with patch("auth_service.services.booking_tenant.get_supabase_admin",
               return_value=_sb_returning([SETTINGS_ROW])):
        cfg = booking_tenant.load_tenant_by_slug("acme")
    assert cfg is not None
    assert cfg.tenant_id == "t1"
    assert cfg.timezone == "Europe/Berlin"
    assert cfg.calendar_provider == "none"


def test_load_by_slug_unknown_returns_none():
    with patch("auth_service.services.booking_tenant.get_supabase_admin",
               return_value=_sb_returning([])):
        assert booking_tenant.load_tenant_by_slug("nope") is None


def test_load_by_slug_inactive_returns_none():
    row = {**SETTINGS_ROW, "is_active": False}
    with patch("auth_service.services.booking_tenant.get_supabase_admin",
               return_value=_sb_returning([row])):
        assert booking_tenant.load_tenant_by_slug("acme") is None
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_tenant.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.booking_tenant'`

- [ ] **Step 3: Write the implementation**

```python
# backend/auth_service/services/booking_tenant.py
"""Resolve a tenant's booking configuration from booking_settings. A 'tenant'
is a project; the public_slug is the addressing key used by the widget."""

from __future__ import annotations

from dataclasses import dataclass

from .supabase_client import get_supabase_admin

_FIELDS = (
    "tenant_id, public_slug, timezone, locale, business_name, "
    "owner_notification_email, email_from_name, meeting_url, slot_granularity_min, "
    "reminders_enabled, reminder_offsets_min, calendar_provider, is_active"
)


@dataclass(frozen=True)
class TenantConfig:
    tenant_id: str
    public_slug: str
    timezone: str
    locale: str
    business_name: str | None
    owner_notification_email: str
    email_from_name: str | None
    meeting_url: str
    slot_granularity_min: int
    reminders_enabled: bool
    reminder_offsets_min: list[int]
    calendar_provider: str
    is_active: bool


def _to_config(row: dict) -> TenantConfig:
    return TenantConfig(
        tenant_id=row["tenant_id"],
        public_slug=row["public_slug"],
        timezone=row["timezone"],
        locale=row.get("locale") or "en",
        business_name=row.get("business_name"),
        owner_notification_email=row["owner_notification_email"],
        email_from_name=row.get("email_from_name"),
        meeting_url=row.get("meeting_url") or "",
        slot_granularity_min=row.get("slot_granularity_min") or 15,
        reminders_enabled=bool(row.get("reminders_enabled")),
        reminder_offsets_min=list(row.get("reminder_offsets_min") or []),
        calendar_provider=row.get("calendar_provider") or "none",
        is_active=bool(row.get("is_active")),
    )


def _load_where(column: str, value: str) -> TenantConfig | None:
    sb = get_supabase_admin()
    res = sb.table("booking_settings").select(_FIELDS).eq(column, value).limit(1).execute()
    rows = res.data or []
    if not rows:
        return None
    cfg = _to_config(rows[0])
    return cfg if cfg.is_active else None


def load_tenant_by_slug(slug: str) -> TenantConfig | None:
    return _load_where("public_slug", slug)


def load_tenant_by_id(tenant_id: str) -> TenantConfig | None:
    return _load_where("tenant_id", tenant_id)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest auth_service/tests/test_booking_tenant.py -v`
Expected: PASS (3 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/booking_tenant.py backend/auth_service/tests/test_booking_tenant.py
git commit -m "feat(booking): add tenant config resolution"
```

---

## Task 4: `booking_availability.py` — multi-resource DST-aware slot engine

This rewrites the pure engine. Build it in three sub-steps (open windows → free-for-resource → multi-resource union + assignment), each with tests.

**Files:**
- Modify: `backend/auth_service/services/booking_availability.py` (full rewrite)
- Modify: `backend/auth_service/tests/test_booking_availability.py` (full rewrite)

### 4.1 — open windows + candidate starts (DST-aware)

- [ ] **Step 1: Write the failing test**

Replace the entire contents of `test_booking_availability.py` with:

```python
from datetime import date, datetime, time
from zoneinfo import ZoneInfo

from auth_service.services.booking_availability import (
    ResourceAvailability,
    available_starts,
    free_resource_ids_at,
    open_windows_utc,
)

UTC = ZoneInfo("UTC")


def test_open_windows_converts_local_hours_to_utc():
    # Wednesday in Europe/Bucharest (EEST, +3 in June). 09:00-18:00 local.
    windows = open_windows_utc(
        day=date(2026, 6, 10), tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))], exception=None,
    )
    assert windows == [(datetime(2026, 6, 10, 6, 0, tzinfo=UTC),
                        datetime(2026, 6, 10, 15, 0, tzinfo=UTC))]


def test_open_windows_split_shift():
    windows = open_windows_utc(
        day=date(2026, 6, 10), tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(12, 0)), (time(14, 0), time(18, 0))], exception=None,
    )
    assert len(windows) == 2


def test_open_windows_closed_exception_zeroes_day():
    windows = open_windows_utc(
        day=date(2026, 6, 10), tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))],
        exception={"is_closed": True, "start_time": None, "end_time": None},
    )
    assert windows == []


def test_open_windows_custom_hours_exception_replaces():
    windows = open_windows_utc(
        day=date(2026, 6, 10), tz_name="Europe/Bucharest",
        hours=[(time(9, 0), time(18, 0))],
        exception={"is_closed": False, "start_time": time(10, 0), "end_time": time(12, 0)},
    )
    assert windows == [(datetime(2026, 6, 10, 7, 0, tzinfo=UTC),
                        datetime(2026, 6, 10, 9, 0, tzinfo=UTC))]


def test_dst_spring_forward_gap_is_skipped():
    # Europe/Berlin spring-forward 2026-03-29: 02:00->03:00 local. Hours 01:00-04:00
    # local => 00:00..02:00 UTC (no 02:xx local exists). One contiguous UTC window.
    windows = open_windows_utc(
        day=date(2026, 3, 29), tz_name="Europe/Berlin",
        hours=[(time(1, 0), time(4, 0))], exception=None,
    )
    # 01:00 CET = 00:00 UTC; 04:00 CEST = 02:00 UTC.
    assert windows == [(datetime(2026, 3, 29, 0, 0, tzinfo=UTC),
                        datetime(2026, 3, 29, 2, 0, tzinfo=UTC))]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_availability.py -v`
Expected: FAIL with `ImportError: cannot import name 'open_windows_utc'`

- [ ] **Step 3: Write the implementation (first slice)**

Replace the entire contents of `booking_availability.py` with the following. (Later sub-tasks add `free_resource_ids_at` and `available_starts`; write the whole file now so imports resolve, then the next tests exercise the rest.)

```python
"""Pure multi-resource availability math for booking — no I/O, fully unit-tested.

All instants in and out are tz-aware UTC. Working hours are tenant-local `time`s
converted to UTC per day (DST-aware via zoneinfo). A booking occupies a *guard*
interval = [start - buffer_before, start + duration + buffer_after); a slot is
free on a resource when its guard interval overlaps none of that resource's
existing guard intervals. A slot is OFFERED when >= 1 eligible resource is free.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")

# Window/interval = (start_utc, end_utc), both tz-aware UTC.
Interval = tuple[datetime, datetime]


@dataclass(frozen=True)
class ResourceAvailability:
    """One eligible resource's inputs for a single day."""
    resource_id: str
    hours: list[tuple[time, time]]           # local opening hours for this weekday
    exception: dict | None                   # {"is_closed", "start_time", "end_time"} or None
    busy: list[Interval] = field(default_factory=list)  # existing guard intervals (UTC)


def open_windows_utc(
    *, day: date, tz_name: str, hours: list[tuple[time, time]], exception: dict | None
) -> list[Interval]:
    """Open intervals for `day` in UTC. `exception` (if given) overrides: closed
    => [] ; custom start/end => replaces `hours`."""
    if exception is not None:
        if exception.get("is_closed"):
            return []
        if exception.get("start_time") and exception.get("end_time"):
            hours = [(exception["start_time"], exception["end_time"])]
    tz = ZoneInfo(tz_name)
    out: list[Interval] = []
    for start_t, end_t in hours:
        s = datetime.combine(day, start_t, tzinfo=tz).astimezone(_UTC)
        e = datetime.combine(day, end_t, tzinfo=tz).astimezone(_UTC)
        if e > s:
            out.append((s, e))
    return out


def _candidate_starts(*, windows: list[Interval], duration_min: int, granularity_min: int) -> list[datetime]:
    starts: list[datetime] = []
    for w_start, w_end in windows:
        cursor = w_start
        while cursor + timedelta(minutes=duration_min) <= w_end:
            starts.append(cursor)
            cursor += timedelta(minutes=granularity_min)
    return starts


def _guard(start_utc: datetime, *, duration_min: int, buffer_before_min: int, buffer_after_min: int) -> Interval:
    return (
        start_utc - timedelta(minutes=buffer_before_min),
        start_utc + timedelta(minutes=duration_min + buffer_after_min),
    )


def _overlaps_any(interval: Interval, busy: list[Interval]) -> bool:
    g0, g1 = interval
    return any(b0 < g1 and g0 < b1 for (b0, b1) in busy)


def _free_starts_for_resource(
    *, day: date, tz_name: str, res: ResourceAvailability,
    duration_min: int, buffer_before_min: int, buffer_after_min: int, granularity_min: int,
) -> set[datetime]:
    windows = open_windows_utc(day=day, tz_name=tz_name, hours=res.hours, exception=res.exception)
    free: set[datetime] = set()
    for s in _candidate_starts(windows=windows, duration_min=duration_min, granularity_min=granularity_min):
        g = _guard(s, duration_min=duration_min,
                   buffer_before_min=buffer_before_min, buffer_after_min=buffer_after_min)
        if not _overlaps_any(g, res.busy):
            free.add(s)
    return free


def available_starts(
    *, day: date, now_utc: datetime, tz_name: str,
    duration_min: int, buffer_before_min: int, buffer_after_min: int,
    granularity_min: int, lead_time_min: int, max_advance_days: int,
    resources: list[ResourceAvailability],
) -> list[datetime]:
    """Sorted unique UTC starts where >= 1 eligible resource is free, after
    lead-time and max-advance filters."""
    today_host = now_utc.astimezone(ZoneInfo(tz_name)).date()
    if day < today_host or day > today_host + timedelta(days=max_advance_days):
        return []
    earliest = now_utc + timedelta(minutes=lead_time_min)
    horizon = now_utc + timedelta(days=max_advance_days)
    union: set[datetime] = set()
    for res in resources:
        union |= _free_starts_for_resource(
            day=day, tz_name=tz_name, res=res, duration_min=duration_min,
            buffer_before_min=buffer_before_min, buffer_after_min=buffer_after_min,
            granularity_min=granularity_min,
        )
    return sorted(s for s in union if earliest <= s <= horizon)


def free_resource_ids_at(
    *, start_utc: datetime, day: date, tz_name: str,
    duration_min: int, buffer_before_min: int, buffer_after_min: int, granularity_min: int,
    resources: list[ResourceAvailability],
) -> list[str]:
    """Resources whose schedule offers `start_utc` and whose guard interval is
    free. Used to assign a concrete resource at booking time."""
    out: list[str] = []
    for res in resources:
        if start_utc in _free_starts_for_resource(
            day=day, tz_name=tz_name, res=res, duration_min=duration_min,
            buffer_before_min=buffer_before_min, buffer_after_min=buffer_after_min,
            granularity_min=granularity_min,
        ):
            out.append(res.resource_id)
    return out
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest auth_service/tests/test_booking_availability.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/booking_availability.py backend/auth_service/tests/test_booking_availability.py
git commit -m "feat(booking): DST-aware open-windows engine"
```

### 4.2 — free/buffers/lead/advance + multi-resource + assignment

- [ ] **Step 1: Append the failing tests**

Append to `test_booking_availability.py`:

```python
def _res(rid, busy=()):
    return ResourceAvailability(
        resource_id=rid, hours=[(time(9, 0), time(18, 0))], exception=None, busy=list(busy)
    )


COMMON_STARTS = dict(
    tz_name="Europe/Bucharest", duration_min=45, buffer_before_min=0,
    buffer_after_min=0, granularity_min=45, lead_time_min=120, max_advance_days=120,
)


def test_available_starts_basic_count():
    starts = available_starts(
        day=date(2026, 6, 10), now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1")], **COMMON_STARTS,
    )
    # 09:00-18:00, 45-min grid => 12 slots (last 17:15).
    assert len(starts) == 12
    assert starts[0] == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)  # 09:00 EEST


def test_lead_time_drops_near_slots():
    starts = available_starts(
        day=date(2026, 6, 10), now_utc=datetime(2026, 6, 10, 5, 30, tzinfo=UTC),
        resources=[_res("r1")], **COMMON_STARTS,
    )
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) not in starts   # within 2h notice
    assert datetime(2026, 6, 10, 7, 30, tzinfo=UTC) in starts


def test_buffer_blocks_adjacent_slot():
    # An existing booking occupies the guard 07:15-08:30 UTC. With 15-min buffers,
    # the 06:45 UTC grid slot's guard is [06:30, 07:45) which overlaps it -> dropped.
    # The 06:00 grid slot's guard [05:45, 07:00) does NOT overlap -> stays free.
    busy = [(datetime(2026, 6, 10, 7, 15, tzinfo=UTC), datetime(2026, 6, 10, 8, 30, tzinfo=UTC))]
    starts = available_starts(
        day=date(2026, 6, 10), now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1", busy)],
        **{**COMMON_STARTS, "buffer_before_min": 15, "buffer_after_min": 15},
    )
    assert datetime(2026, 6, 10, 6, 45, tzinfo=UTC) not in starts
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) in starts


def test_slot_offered_if_any_resource_free():
    busy = [(datetime(2026, 6, 10, 6, 0, tzinfo=UTC), datetime(2026, 6, 10, 6, 45, tzinfo=UTC))]
    starts = available_starts(
        day=date(2026, 6, 10), now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1", busy), _res("r2")], **COMMON_STARTS,
    )
    # r1's 09:00 is taken but r2 is free -> still offered.
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) in starts


def test_free_resource_ids_excludes_busy_resource():
    busy = [(datetime(2026, 6, 10, 6, 0, tzinfo=UTC), datetime(2026, 6, 10, 6, 45, tzinfo=UTC))]
    free = free_resource_ids_at(
        start_utc=datetime(2026, 6, 10, 6, 0, tzinfo=UTC), day=date(2026, 6, 10),
        tz_name="Europe/Bucharest", duration_min=45, buffer_before_min=0,
        buffer_after_min=0, granularity_min=45,
        resources=[_res("r1", busy), _res("r2")],
    )
    assert free == ["r2"]


def test_max_advance_boundary():
    starts = available_starts(
        day=date(2026, 10, 10), now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        resources=[_res("r1")], **{**COMMON_STARTS, "max_advance_days": 30},
    )
    assert starts == []
```

- [ ] **Step 2: Run tests to verify they pass**

Run: `cd backend && pytest auth_service/tests/test_booking_availability.py -v`
Expected: PASS (11 passed) — the implementation from 4.1 already covers these.

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/tests/test_booking_availability.py
git commit -m "test(booking): multi-resource, buffer, lead/advance engine coverage"
```

---

## Task 5: `booking_repo.py` — booking DB I/O

**Files:**
- Create: `backend/auth_service/services/booking_repo.py`
- Test: `backend/auth_service/tests/test_booking_repo.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_repo.py
from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from auth_service.services import booking_repo
from auth_service.services.booking_repo import BookingConflict

UTC = ZoneInfo("UTC")


def _sb():
    sb = MagicMock()
    for m in ["table", "select", "insert", "update", "upsert", "eq", "in_",
              "gte", "lte", "lt", "gt", "limit", "order"]:
        getattr(sb, m).return_value = sb
    return sb


def _exec(sb, data):
    sb.execute.return_value = type("R", (), {"data": data})()
    return sb


def test_upsert_customer_returns_id():
    sb = _exec(_sb(), [{"id": "c1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        cid = booking_repo.upsert_customer(
            tenant_id="t1", name="Jane", email="j@a.com", phone=None,
            locale="en", timezone="Europe/London",
        )
    assert cid == "c1"


def test_insert_booking_translates_exclusion_violation():
    sb = _sb()
    sb.execute.side_effect = Exception('duplicate key value ... 23P01 conflicting')
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        with pytest.raises(BookingConflict):
            booking_repo.insert_booking(
                tenant_id="t1", service_id="s1", resource_id="r1", customer_id="c1",
                start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
                end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
                guard_start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
                guard_end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
                manage_token_hash="h", source="widget", notes=None,
            )


def test_load_booking_by_token_hash_found():
    sb = _exec(_sb(), [{"id": "b1", "status": "confirmed"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        b = booking_repo.load_booking_by_token_hash("h")
    assert b["id"] == "b1"


def test_busy_by_resource_groups_guard_intervals():
    rows = [
        {"resource_id": "r1", "guard_start_utc": "2026-06-10T06:00:00+00:00",
         "guard_end_utc": "2026-06-10T06:45:00+00:00"},
        {"resource_id": "r1", "guard_start_utc": "2026-06-10T07:00:00+00:00",
         "guard_end_utc": "2026-06-10T07:45:00+00:00"},
        {"resource_id": "r2", "guard_start_utc": "2026-06-10T06:00:00+00:00",
         "guard_end_utc": "2026-06-10T06:45:00+00:00"},
    ]
    sb = _exec(_sb(), rows)
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        busy = booking_repo.busy_guard_intervals_by_resource(
            tenant_id="t1", resource_ids=["r1", "r2"],
            window_start_utc=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
            window_end_utc=datetime(2026, 6, 11, 0, 0, tzinfo=UTC),
        )
    assert len(busy["r1"]) == 2 and len(busy["r2"]) == 1
    assert busy["r1"][0][0] == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_repo.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.booking_repo'`

- [ ] **Step 3: Write the implementation**

```python
# backend/auth_service/services/booking_repo.py
"""All booking-domain database I/O via the service-role Supabase client.
Authorization (tenant scoping) is the caller's responsibility — every function
takes an explicit tenant_id and filters by it."""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from .supabase_client import get_supabase_admin

_UTC = ZoneInfo("UTC")


class BookingConflict(Exception):
    """Raised when an insert/update loses the no-overlap exclusion race."""


def _is_conflict(exc: Exception) -> bool:
    msg = str(exc).lower()
    return "23p01" in msg or "23505" in msg or "exclusion" in msg or "duplicate key" in msg


# ---------- config reads ----------

def load_active_services(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("booking_services").select("*")
           .eq("tenant_id", tenant_id).eq("is_active", True)
           .order("sort_order").execute())
    return res.data or []


def load_service(tenant_id: str, service_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("booking_services").select("*")
           .eq("tenant_id", tenant_id).eq("id", service_id).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def load_eligible_resources(tenant_id: str, service_id: str) -> list[dict]:
    """Active resources linked to this service via booking_service_resources."""
    sb = get_supabase_admin()
    links = (sb.table("booking_service_resources").select("resource_id")
             .eq("tenant_id", tenant_id).eq("service_id", service_id).execute())
    ids = [r["resource_id"] for r in (links.data or [])]
    if not ids:
        return []
    res = (sb.table("booking_resources").select("*")
           .eq("tenant_id", tenant_id).eq("is_active", True)
           .in_("id", ids).order("sort_order").execute())
    return res.data or []


def load_hours(tenant_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("booking_hours").select("*").eq("tenant_id", tenant_id).execute())
    return res.data or []


def load_exceptions(tenant_id: str, date_from: str, date_to: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("booking_exceptions").select("*")
           .eq("tenant_id", tenant_id).gte("date", date_from).lte("date", date_to).execute())
    return res.data or []


def load_policy(tenant_id: str, service_id: str | None) -> dict | None:
    """Service-specific policy if present, else the tenant default (service_id null)."""
    sb = get_supabase_admin()
    if service_id:
        res = (sb.table("booking_policies").select("*")
               .eq("tenant_id", tenant_id).eq("service_id", service_id).limit(1).execute())
        if res.data:
            return res.data[0]
    res = (sb.table("booking_policies").select("*")
           .eq("tenant_id", tenant_id).is_("service_id", "null").limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def busy_guard_intervals_by_resource(
    *, tenant_id: str, resource_ids: list[str],
    window_start_utc: datetime, window_end_utc: datetime,
) -> dict[str, list[tuple[datetime, datetime]]]:
    """Guard intervals of confirmed+pending bookings overlapping the window,
    grouped by resource_id."""
    out: dict[str, list[tuple[datetime, datetime]]] = {rid: [] for rid in resource_ids}
    if not resource_ids:
        return out
    sb = get_supabase_admin()
    res = (sb.table("bookings").select("resource_id, guard_start_utc, guard_end_utc")
           .eq("tenant_id", tenant_id).in_("resource_id", resource_ids)
           .in_("status", ["pending", "confirmed"])
           .lt("guard_start_utc", window_end_utc.isoformat())
           .gt("guard_end_utc", window_start_utc.isoformat()).execute())
    for r in res.data or []:
        rid = r["resource_id"]
        out.setdefault(rid, []).append((
            datetime.fromisoformat(r["guard_start_utc"]).astimezone(_UTC),
            datetime.fromisoformat(r["guard_end_utc"]).astimezone(_UTC),
        ))
    return out


# ---------- writes ----------

def upsert_customer(*, tenant_id: str, name: str, email: str, phone: str | None,
                    locale: str | None, timezone: str | None) -> str:
    sb = get_supabase_admin()
    res = (sb.table("booking_customers")
           .upsert({"tenant_id": tenant_id, "name": name, "email": email,
                    "phone": phone, "locale": locale, "timezone": timezone},
                   on_conflict="tenant_id,email")
           .execute())
    return (res.data or [{}])[0]["id"]


def insert_booking(*, tenant_id: str, service_id: str, resource_id: str, customer_id: str,
                   start_utc: datetime, end_utc: datetime,
                   guard_start_utc: datetime, guard_end_utc: datetime,
                   manage_token_hash: str, source: str, notes: str | None) -> str:
    sb = get_supabase_admin()
    try:
        res = sb.table("bookings").insert({
            "tenant_id": tenant_id, "service_id": service_id, "resource_id": resource_id,
            "customer_id": customer_id, "status": "confirmed",
            "start_utc": start_utc.isoformat(), "end_utc": end_utc.isoformat(),
            "guard_start_utc": guard_start_utc.isoformat(),
            "guard_end_utc": guard_end_utc.isoformat(),
            "manage_token_hash": manage_token_hash, "source": source, "notes": notes,
        }).execute()
    except Exception as exc:  # noqa: BLE001
        if _is_conflict(exc):
            raise BookingConflict() from exc
        raise
    return (res.data or [{}])[0].get("id")


def update_booking(booking_id: str, fields: dict) -> None:
    sb = get_supabase_admin()
    try:
        sb.table("bookings").update(fields).eq("id", booking_id).execute()
    except Exception as exc:  # noqa: BLE001
        if _is_conflict(exc):
            raise BookingConflict() from exc
        raise


def load_booking_by_token_hash(token_hash: str) -> dict | None:
    sb = get_supabase_admin()
    res = (sb.table("bookings").select("*")
           .eq("manage_token_hash", token_hash).limit(1).execute())
    rows = res.data or []
    return rows[0] if rows else None


def insert_audit(*, tenant_id: str, booking_id: str | None, action: str,
                 actor: str, payload: dict | None = None) -> None:
    sb = get_supabase_admin()
    sb.table("booking_audit_log").insert({
        "tenant_id": tenant_id, "booking_id": booking_id,
        "action": action, "actor": actor, "payload": payload,
    }).execute()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest auth_service/tests/test_booking_repo.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/booking_repo.py backend/auth_service/tests/test_booking_repo.py
git commit -m "feat(booking): add booking data-access repo"
```

---

## Task 6: `calendar_provider.py` — the adapter seam

**Files:**
- Create: `backend/auth_service/services/calendar_provider.py`
- Test: `backend/auth_service/tests/test_calendar_provider.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_calendar_provider.py
from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from auth_service.services import calendar_provider

UTC = ZoneInfo("UTC")


def test_provider_for_none_is_noop():
    p = calendar_provider.provider_for("none")
    assert p.create_event(start_utc=datetime(2099, 1, 1, tzinfo=UTC),
                          end_utc=datetime(2099, 1, 1, 1, tzinfo=UTC),
                          name="x", email="x@x.com", note="", meeting_url="") is None
    assert p.list_busy(datetime(2099, 1, 1, tzinfo=UTC),
                       datetime(2099, 1, 2, tzinfo=UTC)) == []


def test_provider_for_google_delegates_create():
    p = calendar_provider.provider_for("google")
    with (
        patch("auth_service.services.calendar_provider.google_calendar.is_configured", return_value=True),
        patch("auth_service.services.calendar_provider.google_calendar.create_event",
              return_value="evt123") as mk,
    ):
        evt = p.create_event(start_utc=datetime(2099, 1, 1, tzinfo=UTC),
                             end_utc=datetime(2099, 1, 1, 1, tzinfo=UTC),
                             name="Jane", email="j@a.com", note="hi", meeting_url="http://m")
    assert evt == "evt123"
    mk.assert_called_once()
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_calendar_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.calendar_provider'`

- [ ] **Step 3: Write the implementation**

```python
# backend/auth_service/services/calendar_provider.py
"""Calendar adapter seam. The DB is always the source of truth; a provider is
an OPTIONAL mirror. Phase 1 ships Noop (default) and a Google adapter wrapping
the existing google_calendar module. Selected per tenant by
booking_settings.calendar_provider."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from . import google_calendar

Interval = tuple[datetime, datetime]


class CalendarProvider(Protocol):
    def list_busy(self, start_utc: datetime, end_utc: datetime) -> list[Interval]: ...
    def create_event(self, *, start_utc: datetime, end_utc: datetime, name: str,
                     email: str, note: str, meeting_url: str) -> str | None: ...
    def update_event(self, event_id: str, start_utc: datetime, end_utc: datetime) -> None: ...
    def delete_event(self, event_id: str) -> None: ...


class NoopCalendarProvider:
    def list_busy(self, start_utc: datetime, end_utc: datetime) -> list[Interval]:
        return []
    def create_event(self, *, start_utc, end_utc, name, email, note, meeting_url) -> str | None:
        return None
    def update_event(self, event_id, start_utc, end_utc) -> None:
        return None
    def delete_event(self, event_id) -> None:
        return None


class GoogleCalendarProvider:
    def list_busy(self, start_utc: datetime, end_utc: datetime) -> list[Interval]:
        if not google_calendar.is_configured():
            return []
        return google_calendar.busy_intervals(start_utc, end_utc)
    def create_event(self, *, start_utc, end_utc, name, email, note, meeting_url) -> str | None:
        if not google_calendar.is_configured():
            return None
        return google_calendar.create_event(
            start_utc=start_utc, end_utc=end_utc, name=name, email=email,
            note=note, meeting_url=meeting_url)
    def update_event(self, event_id, start_utc, end_utc) -> None:
        if google_calendar.is_configured():
            google_calendar.update_event_time(event_id, start_utc, end_utc)
    def delete_event(self, event_id) -> None:
        if google_calendar.is_configured():
            google_calendar.delete_event(event_id)


def provider_for(name: str) -> CalendarProvider:
    return GoogleCalendarProvider() if name == "google" else NoopCalendarProvider()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest auth_service/tests/test_calendar_provider.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/calendar_provider.py backend/auth_service/tests/test_calendar_provider.py
git commit -m "feat(booking): add calendar-provider adapter seam"
```

---

## Task 7: Parametrize email host recipient

The host-notification / cancellation / reschedule emails hardcode `settings.BOOKING_HOST_EMAIL`. Make the recipient a parameter so each tenant's `owner_notification_email` is used. Branding stays as-is (P4).

**Files:**
- Modify: `backend/auth_service/services/booking_email.py:159-170`
- Modify: `backend/auth_service/services/booking_manage_email.py:154-179`
- Test: `backend/auth_service/tests/test_booking_email.py` (add one test)

- [ ] **Step 1: Write the failing test**

Append to `backend/auth_service/tests/test_booking_email.py`:

```python
from unittest.mock import patch

from auth_service.services import booking_email


def test_host_notification_uses_passed_recipient():
    booking = {"name": "Jane", "email": "j@a.com", "note": "", "when_label": "soon",
               "start_utc": None, "end_utc": None}
    with patch("auth_service.services.booking_email._send", return_value={}) as snd:
        booking_email.send_host_notification(
            booking=booking, meeting_url="", host_email="owner@tenant.com")
    assert snd.call_args.kwargs["to_email"] == "owner@tenant.com"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_email.py::test_host_notification_uses_passed_recipient -v`
Expected: FAIL with `TypeError: send_host_notification() got an unexpected keyword argument 'host_email'`

- [ ] **Step 3: Edit `booking_email.send_host_notification`**

Change the signature and the `to_email` (booking_email.py:159-170):

```python
def send_host_notification(*, booking: dict, meeting_url: str, host_email: str | None = None) -> dict:
    link = f"Join: {meeting_url}\n" if meeting_url else ""
    text = (
        f"New call booked\n\nWhen: {booking['when_label']}\nName: {booking['name']}\n"
        f"Email: {booking['email']}\nNote: {booking.get('note') or '-'}\n{link}"
    )
    return _send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        subject=f"New booking — {booking['name']}",
        html_body=render_host_html(booking=booking, meeting_url=meeting_url),
        text_body=text,
    )
```

- [ ] **Step 4: Edit `booking_manage_email` host recipients**

In `send_cancellation` (booking_manage_email.py:154) and `send_reschedule` (booking_manage_email.py:169), add a `host_email: str | None = None` keyword param and replace the two host `to_email=settings.BOOKING_HOST_EMAIL` occurrences (lines 156, 175) with `to_email=host_email or settings.BOOKING_HOST_EMAIL`.

```python
def send_cancellation(*, name: str, client_email: str, host_when: str, client_when: str,
                      host_email: str | None = None) -> None:
    _safe_send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        ...
```
```python
def send_reschedule(
    *, name: str, client_email: str, old_host_when: str, new_host_when: str,
    new_client_when: str, meeting_url: str, manage_url: str,
    new_start: datetime, new_end: datetime, host_email: str | None = None,
) -> None:
    _safe_send(
        to_email=host_email or settings.BOOKING_HOST_EMAIL,
        ...
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `cd backend && pytest auth_service/tests/test_booking_email.py auth_service/tests/test_booking_manage_email.py -v`
Expected: PASS (all existing + the new test).

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/services/booking_email.py backend/auth_service/services/booking_manage_email.py backend/auth_service/tests/test_booking_email.py
git commit -m "feat(booking): parametrize host email recipient per tenant"
```

### CHECKPOINT (end of Part A)
Run the full booking unit suite: `cd backend && pytest auth_service/tests/ -k booking -v`. All domain-layer tests pass. The DB is still on the old schema (migration not applied). Review before Part B.

---

# PART B — Tenant-scoped API + cutover

## Task 8: Router rewrite — slug-scoped endpoints

Rewrite `routers/booking.py` so the booking flow uses the domain layer and resolves a tenant. Add shared helpers + the new slug-scoped routes. Legacy shims are added in Task 9.

**Files:**
- Modify: `backend/auth_service/routers/booking.py` (full rewrite)
- Test: `backend/auth_service/tests/test_booking_slug_router.py` (new)

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_slug_router.py
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC = ZoneInfo("UTC")

TENANT = TenantConfig(
    tenant_id="t1", public_slug="acme", timezone="Europe/Bucharest", locale="en",
    business_name="Acme", owner_notification_email="owner@acme.com",
    email_from_name="Acme", meeting_url="", slot_granularity_min=45,
    reminders_enabled=True, reminder_offsets_min=[60], calendar_provider="none",
    is_active=True,
)
SERVICE = {"id": "s1", "tenant_id": "t1", "name": "Cut", "duration_min": 45,
           "buffer_before_min": 0, "buffer_after_min": 0, "lead_time_min": 120,
           "max_advance_days": 120, "is_active": True, "sort_order": 0}
RESOURCE = {"id": "r1", "tenant_id": "t1", "name": "Chair 1", "is_active": True, "sort_order": 0}


@pytest.fixture
def client():
    return TestClient(app)


def test_unknown_slug_404(client):
    with patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=None):
        r = client.get("/booking/nope/services")
    assert r.status_code == 404


def test_services_lists_active(client):
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SERVICE]),
    ):
        r = client.get("/booking/acme/services")
    assert r.status_code == 200
    assert r.json()["services"][0]["id"] == "s1"


def test_create_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", return_value="b1"),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch("auth_service.routers.booking.booking_email.send_host_notification"),
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation"),
    ):
        r = client.post("/booking/acme", json={
            "service_id": "s1",
            "start_utc": "2099-06-10T06:00:00+00:00",
            "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
        })
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["booking_id"] == "b1"
    assert "/manage/" in body["manage_url"]


def test_create_conflict_returns_409(client, monkeypatch):
    from auth_service.services.booking_repo import BookingConflict
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking.booking_repo.load_eligible_resources", return_value=[RESOURCE]),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", side_effect=BookingConflict()),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
    ):
        r = client.post("/booking/acme", json={
            "service_id": "s1",
            "start_utc": "2099-06-10T06:00:00+00:00",
            "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
        })
    assert r.status_code == 409
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_slug_router.py -v`
Expected: FAIL (routes/`_build_resource_availability`/`_free_resource_for` don't exist yet).

- [ ] **Step 3: Rewrite `routers/booking.py`**

Replace the file with the following. (Legacy shim routes are added in Task 9; this step delivers the slug-scoped API + shared helpers.)

```python
"""Multi-tenant booking API. Public booking flows are keyed by a tenant
public_slug resolved server-side; the anon/browser never sends a tenant id.
Authorization is app-layer with the service-role client (RLS stays
enabled-no-policy). The slot engine and DB I/O live in the booking_* services."""

from __future__ import annotations

import hashlib
import logging
import re
import secrets
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config import settings
from ..core.limiter import client_ip, limiter
from ..services import (
    booking_availability,
    booking_email,
    booking_manage_email,
    booking_repo,
    booking_tenant,
    calendar_provider,
)
from ..services.booking_availability import ResourceAvailability
from ..services.booking_repo import BookingConflict
from ..services.booking_tenant import TenantConfig

router = APIRouter(prefix="/booking", tags=["booking"])
log = logging.getLogger(__name__)

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_UTC = ZoneInfo("UTC")


def _hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def _require_tenant(slug: str) -> TenantConfig:
    cfg = booking_tenant.load_tenant_by_slug(slug)
    if cfg is None:
        raise HTTPException(status_code=404, detail="Unknown booking page")
    return cfg


def _hours_for_weekday(hours_rows: list[dict], resource_id: str, weekday: int) -> list[tuple[time, time]]:
    """Per-resource hours if the resource has its own rows, else business-level
    (resource_id null). `weekday` is Postgres dow (0=Sun)."""
    own = [h for h in hours_rows if h.get("resource_id") == resource_id]
    src = own if own else [h for h in hours_rows if h.get("resource_id") is None]
    out: list[tuple[time, time]] = []
    for h in src:
        if h["weekday"] == weekday:
            out.append((time.fromisoformat(h["start_time"]), time.fromisoformat(h["end_time"])))
    return out


def _exception_for(exc_rows: list[dict], resource_id: str, day: date) -> dict | None:
    iso = day.isoformat()
    cands = [e for e in exc_rows if e["date"] == iso
             and (e.get("resource_id") == resource_id or e.get("resource_id") is None)]
    if not cands:
        return None
    e = cands[0]
    return {
        "is_closed": e["is_closed"],
        "start_time": time.fromisoformat(e["start_time"]) if e.get("start_time") else None,
        "end_time": time.fromisoformat(e["end_time"]) if e.get("end_time") else None,
    }


def _build_resource_availability(
    *, cfg: TenantConfig, resources: list[dict], hours_rows: list[dict],
    exc_rows: list[dict], day: date, window_start: datetime, window_end: datetime,
) -> list[ResourceAvailability]:
    dow = (day.isoweekday() % 7)  # ISO Mon=1..Sun=7 -> dow Sun=0..Sat=6
    rids = [r["id"] for r in resources]
    busy = booking_repo.busy_guard_intervals_by_resource(
        tenant_id=cfg.tenant_id, resource_ids=rids,
        window_start_utc=window_start, window_end_utc=window_end)
    # Calendar busy (tenant #1 / google) blocks every resource — it is the host's
    # personal calendar. Noop providers return []. Best-effort: a fetch failure
    # falls back to DB-only availability.
    cal_busy: list[tuple[datetime, datetime]] = []
    if cfg.calendar_provider != "none":
        try:
            cal_busy = calendar_provider.provider_for(cfg.calendar_provider).list_busy(
                window_start, window_end)
        except Exception:  # noqa: BLE001
            log.exception("calendar busy fetch failed; supabase-only availability")
    out: list[ResourceAvailability] = []
    for r in resources:
        out.append(ResourceAvailability(
            resource_id=r["id"],
            hours=_hours_for_weekday(hours_rows, r["id"], dow),
            exception=_exception_for(exc_rows, r["id"], day),
            busy=busy.get(r["id"], []) + cal_busy,
        ))
    return out


def _availability_for_day(*, cfg: TenantConfig, service: dict, day: date,
                          now_utc: datetime) -> list[datetime]:
    resources = booking_repo.load_eligible_resources(cfg.tenant_id, service["id"])
    if not resources:
        return []
    tz = ZoneInfo(cfg.timezone)
    win_start = datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(_UTC) - timedelta(days=1)
    win_end = win_start + timedelta(days=3)
    hours_rows = booking_repo.load_hours(cfg.tenant_id)
    exc_rows = booking_repo.load_exceptions(cfg.tenant_id, day.isoformat(), day.isoformat())
    avail = _build_resource_availability(
        cfg=cfg, resources=resources, hours_rows=hours_rows, exc_rows=exc_rows,
        day=day, window_start=win_start, window_end=win_end)
    return booking_availability.available_starts(
        day=day, now_utc=now_utc, tz_name=cfg.timezone,
        duration_min=service["duration_min"],
        buffer_before_min=service["buffer_before_min"],
        buffer_after_min=service["buffer_after_min"],
        granularity_min=cfg.slot_granularity_min,
        lead_time_min=service["lead_time_min"],
        max_advance_days=service["max_advance_days"],
        resources=avail)


def _free_resource_for(*, cfg: TenantConfig, service: dict, start_utc: datetime,
                       now_utc: datetime) -> str | None:
    """Least-loaded free eligible resource for `start_utc`, or None."""
    resources = booking_repo.load_eligible_resources(cfg.tenant_id, service["id"])
    if not resources:
        return None
    day = start_utc.astimezone(ZoneInfo(cfg.timezone)).date()
    tz = ZoneInfo(cfg.timezone)
    win_start = datetime.combine(day, time(0, 0), tzinfo=tz).astimezone(_UTC) - timedelta(days=1)
    win_end = win_start + timedelta(days=3)
    hours_rows = booking_repo.load_hours(cfg.tenant_id)
    exc_rows = booking_repo.load_exceptions(cfg.tenant_id, day.isoformat(), day.isoformat())
    avail = _build_resource_availability(
        cfg=cfg, resources=resources, hours_rows=hours_rows, exc_rows=exc_rows,
        day=day, window_start=win_start, window_end=win_end)
    free = booking_availability.free_resource_ids_at(
        start_utc=start_utc, day=day, tz_name=cfg.timezone,
        duration_min=service["duration_min"],
        buffer_before_min=service["buffer_before_min"],
        buffer_after_min=service["buffer_after_min"],
        granularity_min=cfg.slot_granularity_min, resources=avail)
    # least-loaded = fewest existing busy intervals among free resources
    busy_count = {r.resource_id: len(r.busy) for r in avail}
    free.sort(key=lambda rid: busy_count.get(rid, 0))
    return free[0] if free else None


def _when_label(start_utc: datetime, tz_name: str) -> str:
    local = start_utc.astimezone(ZoneInfo(tz_name))
    return local.strftime("%a, %d %b %Y · %H:%M ") + f"({tz_name})"


# ---------- slug-scoped public API ----------

@router.get("/{slug}/services")
def list_services(slug: str) -> JSONResponse:
    cfg = _require_tenant(slug)
    services = booking_repo.load_active_services(cfg.tenant_id)
    return JSONResponse(content={"services": [
        {"id": s["id"], "name": s["name"], "duration_min": s["duration_min"]}
        for s in services
    ]})


@router.get("/{slug}/availability")
def availability(slug: str, service_id: str,
                 from_: str = Query(..., alias="from"), to: str = Query(...)) -> JSONResponse:
    cfg = _require_tenant(slug)
    service = booking_repo.load_service(cfg.tenant_id, service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    now = datetime.now(UTC)
    days: list[str] = []
    slots: list[str] = []
    cur = d0
    while cur <= d1:
        starts = _availability_for_day(cfg=cfg, service=service, day=cur, now_utc=now)
        if starts:
            days.append(cur.isoformat())
            slots.extend(s.isoformat() for s in starts)
        cur += timedelta(days=1)
    return JSONResponse(content={"days": days, "slots": slots})


class CustomerIn(BaseModel):
    name: str
    email: str
    phone: str = ""
    locale: str = ""
    tz: str = ""


class CreateIn(BaseModel):
    service_id: str
    resource_id: str = ""
    start_utc: str
    customer: CustomerIn
    website: str = ""  # honeypot


@router.post("/{slug}")
@limiter.limit("5/hour", key_func=client_ip)
async def create_booking(request: Request, slug: str, body: CreateIn) -> JSONResponse:
    cfg = _require_tenant(slug)
    return _create_core(cfg, body)


def _create_core(cfg: TenantConfig, body: CreateIn) -> JSONResponse:
    """Shared create path for the slug route and the tenant-#1 legacy shim.
    Sync (supabase-py is sync); both callers are async route handlers."""
    if body.website.strip():
        return JSONResponse(content={"success": True})
    name = body.customer.name.strip()
    email = body.customer.email.strip()
    if not name or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid booking")
    service = booking_repo.load_service(cfg.tenant_id, body.service_id)
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        start = datetime.fromisoformat(body.start_utc).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad start_utc") from exc

    now = datetime.now(UTC)
    resource_id = _free_resource_for(cfg=cfg, service=service, start_utc=start, now_utc=now)
    if resource_id is None:
        raise HTTPException(status_code=409, detail="That time was just taken")

    end = start + timedelta(minutes=service["duration_min"])
    guard_start = start - timedelta(minutes=service["buffer_before_min"])
    guard_end = end + timedelta(minutes=service["buffer_after_min"])
    raw_token = secrets.token_urlsafe(32)

    customer_id = booking_repo.upsert_customer(
        tenant_id=cfg.tenant_id, name=name, email=email,
        phone=body.customer.phone or None, locale=body.customer.locale or cfg.locale,
        timezone=body.customer.tz or cfg.timezone)
    try:
        booking_id = booking_repo.insert_booking(
            tenant_id=cfg.tenant_id, service_id=service["id"], resource_id=resource_id,
            customer_id=customer_id, start_utc=start, end_utc=end,
            guard_start_utc=guard_start, guard_end_utc=guard_end,
            manage_token_hash=_hash_token(raw_token), source="widget",
            notes=None)
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail="That time was just taken") from exc

    booking_repo.insert_audit(tenant_id=cfg.tenant_id, booking_id=booking_id,
                              action="create", actor="customer",
                              payload={"resource_id": resource_id})

    provider = calendar_provider.provider_for(cfg.calendar_provider)
    try:
        event_id = provider.create_event(
            start_utc=start, end_utc=end, name=name, email=email,
            note="", meeting_url=cfg.meeting_url)
        if event_id:
            booking_repo.update_booking(booking_id, {"google_event_id": event_id})
    except Exception:  # noqa: BLE001
        log.exception("calendar create failed for booking %s", booking_id)

    manage_url = f"{settings.manage_base_url}/manage/{raw_token}"
    visitor_tz = body.customer.tz or cfg.timezone
    base = {"name": name, "email": email, "note": "", "start_utc": start, "end_utc": end}
    try:
        booking_email.send_host_notification(
            booking={**base, "when_label": _when_label(start, cfg.timezone)},
            meeting_url=cfg.meeting_url, host_email=cfg.owner_notification_email)
    except Exception:  # noqa: BLE001
        log.exception("host email failed")
    try:
        booking_email.send_visitor_confirmation(
            booking={**base, "when_label": _when_label(start, visitor_tz)},
            meeting_url=cfg.meeting_url, manage_url=manage_url)
    except Exception:  # noqa: BLE001
        log.exception("visitor email failed")

    return JSONResponse(content={"success": True, "booking_id": booking_id,
                                 "manage_url": manage_url,
                                 "start": start.isoformat(), "end": end.isoformat()})
```

- [ ] **Step 4: Run test to verify it passes**

Run: `cd backend && pytest auth_service/tests/test_booking_slug_router.py -v`
Expected: PASS (4 passed). Both create tests patch `_free_resource_for`. Run ONLY this file — the legacy `test_booking_router.py`/`test_booking_manage_router.py` will fail until Task 9 restores their routes + rewrites them.

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/booking.py backend/auth_service/tests/test_booking_slug_router.py
git commit -m "feat(booking): tenant slug-scoped services/availability/create API"
```

---

## Task 9: Manage endpoints + legacy shims (keep the live widget working)

Add token-based manage routes (hashed lookup, policy-driven windows) and the legacy non-slug routes bound to tenant #1, plus the cron reminder route, to the rewritten router.

**Files:**
- Modify: `backend/auth_service/routers/booking.py` (append routes)
- Test: `backend/auth_service/tests/test_booking_manage_router.py` (rewrite), `backend/auth_service/tests/test_booking_router.py` (adapt the legacy-shim assertions)

- [ ] **Step 1: Write the failing tests (manage)**

Replace `backend/auth_service/tests/test_booking_manage_router.py` with:

```python
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC = ZoneInfo("UTC")
TENANT = TenantConfig(
    tenant_id="t1", public_slug="acme", timezone="Europe/Bucharest", locale="en",
    business_name="Acme", owner_notification_email="owner@acme.com", email_from_name="Acme",
    meeting_url="", slot_granularity_min=45, reminders_enabled=True,
    reminder_offsets_min=[60], calendar_provider="none", is_active=True,
)
POLICY = {"allow_cancel": True, "cancellation_window_hours": 24, "allow_reschedule": True,
          "reschedule_window_hours": 12, "max_reschedules": 2}


@pytest.fixture
def client():
    return TestClient(app)


def _booking(**over):
    b = {"id": "b1", "tenant_id": "t1", "service_id": "s1", "customer_id": "c1",
         "status": "confirmed", "start_utc": "2099-06-10T06:00:00+00:00",
         "end_utc": "2099-06-10T06:45:00+00:00", "reschedule_count": 0, "google_event_id": None}
    b.update(over)
    return b


def test_manage_get_not_found(client):
    with patch("auth_service.routers.booking.booking_repo.load_booking_by_token_hash", return_value=None):
        r = client.get("/booking/manage/abc")
    assert r.status_code == 200 and r.json()["found"] is False


def test_manage_get_flags(client):
    with (
        patch("auth_service.routers.booking.booking_repo.load_booking_by_token_hash", return_value=_booking()),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
        patch("auth_service.routers.booking.booking_repo.load_customer",
              return_value={"name": "Jane", "email": "j@a.com", "timezone": "Europe/London"}),
    ):
        r = client.get("/booking/manage/abc")
    body = r.json()
    assert body["found"] is True and body["can_cancel"] is True


def test_cancel_too_late_rejected(client):
    from datetime import datetime, timedelta
    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with (
        patch("auth_service.routers.booking.booking_repo.load_booking_by_token_hash",
              return_value=_booking(start_utc=soon)),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
    ):
        r = client.post("/booking/manage/abc/cancel")
    assert r.status_code == 403


def test_cancel_success(client):
    with (
        patch("auth_service.routers.booking.booking_repo.load_booking_by_token_hash", return_value=_booking()),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch("auth_service.routers.booking.booking_repo.load_customer",
              return_value={"name": "Jane", "email": "j@a.com", "timezone": "Europe/London"}),
        patch("auth_service.routers.booking.booking_manage_email.send_cancellation"),
    ):
        r = client.post("/booking/manage/abc/cancel")
    assert r.status_code == 200 and r.json()["success"] is True
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && pytest auth_service/tests/test_booking_manage_router.py -v`
Expected: FAIL (manage routes not defined on the new router yet).

- [ ] **Step 3: Append manage + cron + legacy-shim routes to `routers/booking.py`**

```python
# ---------- manage by token ----------

def _load_for_manage(token: str):
    b = booking_repo.load_booking_by_token_hash(_hash_token(token))
    if not b:
        return None, None, None
    cfg = booking_tenant.load_tenant_by_id(b["tenant_id"])
    policy = booking_repo.load_policy(b["tenant_id"], b.get("service_id"))
    return b, cfg, (policy or {})


# NOTE: GET to match the existing /contact manage page's contract (zero frontend
# change in P1). Before finalizing, open frontend/src/app/(marketing)/manage/[token]/page.tsx
# and confirm every field it reads is present in this response.
@router.get("/manage/{token}")
def manage_get(token: str) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        return JSONResponse(content={"found": False})
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    now = datetime.now(UTC)
    confirmed = b["status"] == "confirmed"
    count = b.get("reschedule_count") or 0
    can_cancel = (confirmed and policy.get("allow_cancel", True)
                  and now <= start - timedelta(hours=policy.get("cancellation_window_hours", 24)))
    can_resched = (confirmed and policy.get("allow_reschedule", True)
                   and now <= start - timedelta(hours=policy.get("reschedule_window_hours", 24))
                   and count < policy.get("max_reschedules", 2))
    return JSONResponse(content={
        "found": True, "status": b["status"], "start_utc": b["start_utc"],
        "end_utc": b["end_utc"], "name": cust.get("name", ""),
        "visitor_timezone": cust.get("timezone") or cfg.timezone, "timezone": cfg.timezone,
        "reschedule_count": count, "max_reschedules": policy.get("max_reschedules", 2),
        "can_cancel": can_cancel, "can_reschedule": can_resched,
    })


@router.post("/manage/{token}/cancel")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_cancel(request: Request, token: str) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    if not policy.get("allow_cancel", True) or datetime.now(UTC) > start - timedelta(
            hours=policy.get("cancellation_window_hours", 24)):
        raise HTTPException(status_code=403, detail="Too late to cancel online")
    provider = calendar_provider.provider_for(cfg.calendar_provider)
    if b.get("google_event_id"):
        try:
            provider.delete_event(b["google_event_id"])
        except Exception:  # noqa: BLE001
            log.exception("calendar delete failed for %s", b["id"])
    booking_repo.update_booking(b["id"], {"status": "cancelled",
                                          "cancelled_at": datetime.now(UTC).isoformat()})
    booking_repo.insert_audit(tenant_id=cfg.tenant_id, booking_id=b["id"],
                              action="cancel", actor="customer")
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    try:
        booking_manage_email.send_cancellation(
            name=cust.get("name", ""), client_email=cust.get("email", ""),
            host_when=_when_label(start, cfg.timezone),
            client_when=_when_label(start, cust.get("timezone") or cfg.timezone),
            host_email=cfg.owner_notification_email)
    except Exception:  # noqa: BLE001
        log.exception("cancellation email failed")
    return JSONResponse(content={"success": True})


class RescheduleIn(BaseModel):
    slot_start: str  # the live /contact widget posts {slot_start}; keep that name


@router.post("/manage/{token}/reschedule")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_reschedule(request: Request, token: str, body: RescheduleIn) -> JSONResponse:
    b, cfg, policy = _load_for_manage(token)
    if not b or cfg is None:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    old_start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    now = datetime.now(UTC)
    if not policy.get("allow_reschedule", True) or now > old_start - timedelta(
            hours=policy.get("reschedule_window_hours", 24)):
        raise HTTPException(status_code=403, detail="Too late to reschedule online")
    if (b.get("reschedule_count") or 0) >= policy.get("max_reschedules", 2):
        raise HTTPException(status_code=403, detail="Reschedule limit reached")
    service = booking_repo.load_service(cfg.tenant_id, b["service_id"])
    if service is None:
        raise HTTPException(status_code=404, detail="Unknown service")
    try:
        new_start = datetime.fromisoformat(body.slot_start).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad slot_start") from exc
    # Free-resource check reuses the same resource where possible; assign fresh.
    resource_id = _free_resource_for(cfg=cfg, service=service, start_utc=new_start, now_utc=now)
    if resource_id is None:
        raise HTTPException(status_code=409, detail="That time was just taken")
    new_end = new_start + timedelta(minutes=service["duration_min"])
    new_token = secrets.token_urlsafe(32)
    try:
        booking_repo.update_booking(b["id"], {
            "start_utc": new_start.isoformat(), "end_utc": new_end.isoformat(),
            "guard_start_utc": (new_start - timedelta(minutes=service["buffer_before_min"])).isoformat(),
            "guard_end_utc": (new_end + timedelta(minutes=service["buffer_after_min"])).isoformat(),
            "resource_id": resource_id,
            "reschedule_count": (b.get("reschedule_count") or 0) + 1,
            "manage_token_hash": _hash_token(new_token),
        })
    except BookingConflict as exc:
        raise HTTPException(status_code=409, detail="That time was just taken") from exc
    booking_repo.insert_audit(tenant_id=cfg.tenant_id, booking_id=b["id"],
                              action="reschedule", actor="customer")
    provider = calendar_provider.provider_for(cfg.calendar_provider)
    if b.get("google_event_id"):
        try:
            provider.update_event(b["google_event_id"], new_start, new_end)
        except Exception:  # noqa: BLE001
            log.exception("calendar patch failed for %s", b["id"])
    cust = booking_repo.load_customer(b["customer_id"]) or {}
    manage_url = f"{settings.manage_base_url}/manage/{new_token}"
    try:
        booking_manage_email.send_reschedule(
            name=cust.get("name", ""), client_email=cust.get("email", ""),
            old_host_when=_when_label(old_start, cfg.timezone),
            new_host_when=_when_label(new_start, cfg.timezone),
            new_client_when=_when_label(new_start, cust.get("timezone") or cfg.timezone),
            meeting_url=cfg.meeting_url, manage_url=manage_url,
            new_start=new_start, new_end=new_end, host_email=cfg.owner_notification_email)
    except Exception:  # noqa: BLE001
        log.exception("reschedule email failed")
    return JSONResponse(content={"success": True, "start": new_start.isoformat(),
                                 "end": new_end.isoformat()})


# ---------- reminders cron ----------

@router.post("/cron/reminders")
async def send_reminders(request: Request) -> JSONResponse:
    secret = request.headers.get("x-cron-secret", "")
    if not settings.BOOKING_CRON_SECRET or secret != settings.BOOKING_CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")
    now = datetime.now(UTC)
    window_end = now + timedelta(minutes=65)
    rows = booking_repo.due_reminders(now_utc=now, window_end_utc=window_end)
    sent = 0
    for b in rows:
        cfg = booking_tenant.load_tenant_by_id(b["tenant_id"])
        if cfg is None or not cfg.reminders_enabled:
            continue
        cust = booking_repo.load_customer(b["customer_id"]) or {}
        start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
        try:
            from ..services import booking_reminder_email
            # No manage link in reminders: only the hash is stored, and the raw
            # token can't be reconstructed. The manage link lives in the
            # confirmation email. (Re-add in P4 if reminders need it.)
            booking_reminder_email.send(
                to_email=cust.get("email", ""), name=cust.get("name", ""), note=b.get("notes"),
                when_label=_when_label(start, cust.get("timezone") or cfg.timezone),
                meeting_url=cfg.meeting_url, manage_url="")
            booking_repo.update_booking(b["id"], {"reminder_sent_at": now.isoformat()})
            sent += 1
        except Exception:  # noqa: BLE001
            log.exception("reminder failed for %s", b.get("id"))
    return JSONResponse(content={"sent": sent})


# ---------- legacy shims (tenant #1; keep the live widget working) ----------

_LEGACY_SLUG = "roman-technologies-website"


@router.get("/availability")
def legacy_availability(from_: str = Query(..., alias="from"), to: str = Query(...)) -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        return JSONResponse(content={"days": []})
    service = services[0]
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    now = datetime.now(UTC)
    days, cur = [], d0
    while cur <= d1:
        if _availability_for_day(cfg=cfg, service=service, day=cur, now_utc=now):
            days.append(cur.isoformat())
        cur += timedelta(days=1)
    return JSONResponse(content={"days": days})


@router.get("/slots")
def legacy_slots(date: str, tz: str = "") -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        return JSONResponse(content={"slots": []})
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad date") from exc
    starts = _availability_for_day(cfg=cfg, service=services[0], day=day, now_utc=datetime.now(UTC))
    return JSONResponse(content={"slots": [s.isoformat() for s in starts]})


class LegacyBookingRequest(BaseModel):
    slot_start: str
    name: str
    email: str
    note: str = ""
    visitor_timezone: str = ""
    website: str = ""


@router.post("")
@limiter.limit("5/hour", key_func=client_ip)
async def legacy_create(request: Request, body: LegacyBookingRequest) -> JSONResponse:
    cfg = _require_tenant(_LEGACY_SLUG)
    services = booking_repo.load_active_services(cfg.tenant_id)
    if not services:
        raise HTTPException(status_code=503, detail="Booking unavailable")
    payload = CreateIn(
        service_id=services[0]["id"], start_utc=body.slot_start,
        customer=CustomerIn(name=body.name, email=body.email, tz=body.visitor_timezone),
        website=body.website)
    # Single code path, no re-entry into the rate-limited route.
    return _create_core(cfg, payload)
```

Then add the two repo helpers used above — append to `booking_repo.py`:

```python
def load_customer(customer_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("booking_customers").select("*").eq("id", customer_id).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


def due_reminders(*, now_utc: datetime, window_end_utc: datetime) -> list[dict]:
    sb = get_supabase_admin()
    res = (sb.table("bookings")
           .select("id, tenant_id, customer_id, notes, start_utc")
           .eq("status", "confirmed").is_("reminder_sent_at", "null")
           .gte("start_utc", now_utc.isoformat()).lte("start_utc", window_end_utc.isoformat())
           .execute())
    return res.data or []
```

The router uses `booking_repo.load_customer` directly; no `_customer_email` helper is needed.

- [ ] **Step 4: Run manage tests to verify they pass**

Run: `cd backend && pytest auth_service/tests/test_booking_manage_router.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Adapt the legacy-shim tests**

In `backend/auth_service/tests/test_booking_router.py`, the legacy routes now resolve tenant #1 and delegate. Update the three DB-touching tests to also patch tenant resolution + the domain calls. Replace `test_slots_returns_iso_starts`, `test_booking_happy_path_inserts_and_emails`, and `test_booking_creates_google_event_when_configured` with versions that patch `booking_tenant.load_tenant_by_slug` → a tenant whose timezone is `Europe/Berlin`, `booking_repo.load_active_services` → `[{"id":"s1","duration_min":45,"buffer_before_min":0,"buffer_after_min":0,"lead_time_min":120,"max_advance_days":120}]`, and `_availability_for_day` / `_free_resource_for` as needed. Concretely, replace the file's body with:

```python
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC = ZoneInfo("UTC")
T1 = TenantConfig(
    tenant_id="a7fccf9f-35ba-4655-baba-6744cab738dc", public_slug="roman-technologies-website",
    timezone="Europe/Berlin", locale="en", business_name="Roman Technologies",
    owner_notification_email="stefanromanpers@gmail.com", email_from_name="Roman Technologies CMS",
    meeting_url="", slot_granularity_min=45, reminders_enabled=True, reminder_offsets_min=[60],
    calendar_provider="none", is_active=True,
)
SVC = {"id": "s1", "duration_min": 45, "buffer_before_min": 0, "buffer_after_min": 0,
       "lead_time_min": 120, "max_advance_days": 120}


@pytest.fixture
def client():
    return TestClient(app)


def test_legacy_slots_returns_iso(client):
    starts = [__import__("datetime").datetime(2099, 6, 10, 7, 0, tzinfo=UTC)]
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
        patch("auth_service.routers.booking._availability_for_day", return_value=starts),
    ):
        r = client.get("/booking/slots?date=2099-06-10&tz=Europe/London")
    assert r.status_code == 200
    assert r.json()["slots"][0].startswith("2099-06-10")


def test_legacy_booking_honeypot(client):
    with patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1), \
         patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]):
        r = client.post("/booking", json={"slot_start": "2099-06-10T06:00:00+00:00",
                                          "name": "Bot", "email": "b@b.com", "website": "x"})
    assert r.status_code == 200 and r.json()["success"] is True


def test_legacy_booking_422_bad_email(client):
    with patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1), \
         patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]):
        r = client.post("/booking", json={"slot_start": "2099-06-10T06:00:00+00:00",
                                          "name": "J", "email": "nope"})
    assert r.status_code == 422


def test_legacy_booking_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_active_services", return_value=[SVC]),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SVC),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", return_value="b1"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch("auth_service.routers.booking.booking_email.send_host_notification") as host,
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation") as vis,
    ):
        r = client.post("/booking", json={"slot_start": "2099-06-10T06:00:00+00:00",
                                          "name": "Jane", "email": "jane@acme.com", "note": "hi",
                                          "visitor_timezone": "Europe/London"})
    assert r.status_code == 200, r.text
    host.assert_called_once()
    vis.assert_called_once()


def test_reminders_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    r = client.post("/booking/cron/reminders")
    assert r.status_code == 403


def test_reminders_sends_and_marks(client, monkeypatch):
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    due = [{"id": "b1", "tenant_id": "t1", "customer_id": "c1", "notes": None,
            "start_utc": "2099-06-10T06:00:00+00:00"}]
    with (
        patch("auth_service.routers.booking.booking_repo.due_reminders", return_value=due),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=T1),
        patch("auth_service.routers.booking.booking_repo.load_customer",
              return_value={"email": "j@a.com", "name": "Jane", "timezone": "Europe/London"}),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.services.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200 and r.json()["sent"] == 1
    snd.assert_called_once()
```

- [ ] **Step 6: Run the full router suite**

Run: `cd backend && pytest auth_service/tests/test_booking_router.py auth_service/tests/test_booking_slug_router.py auth_service/tests/test_booking_manage_router.py -v`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/routers/booking.py backend/auth_service/services/booking_repo.py backend/auth_service/tests/test_booking_router.py backend/auth_service/tests/test_booking_manage_router.py
git commit -m "feat(booking): manage routes, reminders, and tenant-#1 legacy shims"
```

---

## Task 10: Concurrency + cross-tenant isolation integration tests

These require the real DB (the exclusion constraint and tenant filtering can't be mocked). They run against the Supabase project **after** Task 11 applies the migration, but write the test now and mark it to run in the integration pass.

**Files:**
- Create: `backend/auth_service/tests/test_booking_integration.py`

- [ ] **Step 1: Write the integration tests**

```python
# backend/auth_service/tests/test_booking_integration.py
"""DB-backed booking guarantees: no double-book under concurrency, and no
cross-tenant access. Skipped unless RUN_BOOKING_INTEGRATION=1 and the migration
is applied (they write/delete rows in a dedicated test tenant)."""

import concurrent.futures
import os
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from auth_service.services import booking_repo
from auth_service.services.booking_repo import BookingConflict

UTC = ZoneInfo("UTC")
pytestmark = pytest.mark.skipif(
    os.getenv("RUN_BOOKING_INTEGRATION") != "1",
    reason="integration test; set RUN_BOOKING_INTEGRATION=1 after migration",
)

# The E2E test project seeded by the migration's instructions (see Task 11 notes).
TEST_TENANT = os.getenv("BOOKING_TEST_TENANT_ID", "")
TEST_SERVICE = os.getenv("BOOKING_TEST_SERVICE_ID", "")
TEST_RESOURCE = os.getenv("BOOKING_TEST_RESOURCE_ID", "")


def _insert(start):
    cid = booking_repo.upsert_customer(
        tenant_id=TEST_TENANT, name="IT", email="it@test.com", phone=None,
        locale="en", timezone="UTC")
    return booking_repo.insert_booking(
        tenant_id=TEST_TENANT, service_id=TEST_SERVICE, resource_id=TEST_RESOURCE,
        customer_id=cid, start_utc=start, end_utc=start + timedelta(minutes=45),
        guard_start_utc=start, guard_end_utc=start + timedelta(minutes=45),
        manage_token_hash=os.urandom(8).hex(), source="api", notes=None)


def test_concurrent_same_slot_only_one_wins():
    start = datetime(2099, 1, 1, 9, 0, tzinfo=UTC)
    results = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex:
        futs = [ex.submit(_insert, start) for _ in range(8)]
        for f in futs:
            try:
                results.append(f.result())
            except BookingConflict:
                results.append(None)
    assert sum(1 for r in results if r) == 1
    # cleanup
    for r in results:
        if r:
            booking_repo.update_booking(r, {"status": "cancelled"})
```

(Cross-tenant isolation is asserted at the API layer in `test_booking_slug_router.py::test_unknown_slug_404` and by the repo's explicit `tenant_id` filter on every query; a DB-level cross-tenant read test is added here once the test tenant exists — see Task 11 Step 5.)

- [ ] **Step 2: Verify it is collected but skipped**

Run: `cd backend && pytest auth_service/tests/test_booking_integration.py -v`
Expected: `1 skipped` (env var not set).

- [ ] **Step 3: Commit**

```bash
git add backend/auth_service/tests/test_booking_integration.py
git commit -m "test(booking): DB-backed concurrency integration test (gated)"
```

---

## Task 11: Apply the migration + post-migration validation (cutover)

**Files:** none (operational task via Supabase MCP).

- [ ] **Step 1: Back up the 7 live rows**

Via Supabase MCP `execute_sql` on project `xeluydwpgiddbamysgyu`:
```sql
select * from public.bookings;
```
Save the JSON output to `backend/migrations/_backup_bookings_2026_06_05.json` (so a manual restore is possible if the rollback is ever needed).

- [ ] **Step 2: Apply the migration**

Apply `backend/migrations/2026_06_05_booking_multitenant.sql` via Supabase MCP `apply_migration` (name: `2026_06_05_booking_multitenant`).

- [ ] **Step 3: Validate the backfill**

Run via `execute_sql` and confirm each:
```sql
-- 7 rows, all tenant-scoped to tenant #1, all with a guard range:
select count(*) total,
       count(*) filter (where tenant_id = 'a7fccf9f-35ba-4655-baba-6744cab738dc') t1,
       count(*) filter (where guard_range is not null) g,
       count(*) filter (where status='confirmed') confirmed
from public.bookings;
-- expect total=7, t1=7, g=7, confirmed=4

-- the 3 previously-tokened rows now have a hash:
select count(*) from public.bookings where manage_token_hash is not null; -- expect 3

-- exclusion constraint exists:
select conname from pg_constraint where conname = 'bookings_no_overlap'; -- 1 row

-- tenant #1 provisioned:
select (select count(*) from public.booking_settings where tenant_id='a7fccf9f-35ba-4655-baba-6744cab738dc'),
       (select count(*) from public.booking_hours where tenant_id='a7fccf9f-35ba-4655-baba-6744cab738dc'),
       (select count(*) from public.booking_services where tenant_id='a7fccf9f-35ba-4655-baba-6744cab738dc');
-- expect 1, 7, 1
```
If any assertion fails, apply `2026_06_05_booking_multitenant_rollback.sql` and stop.

- [ ] **Step 4: Verify a manage token still resolves**

Take one of the 3 original plaintext tokens from the backup JSON, compute its SHA-256 hex (`python -c "import hashlib;print(hashlib.sha256('<token>'.encode()).hexdigest())"`), and:
```sql
select id, status from public.bookings where manage_token_hash = '<hash>';
```
Expected: the matching booking row — proving migrated links work.

- [ ] **Step 5: Seed an integration test tenant + run the gated tests**

Insert a second `booking_settings`/resource/service for the existing `e2e-test-project` (`7fadaf4f-abbd-4ee5-b486-5e53fa630e01`) so isolation/concurrency tests have a non-#1 tenant. Then export `RUN_BOOKING_INTEGRATION=1`, `BOOKING_TEST_TENANT_ID`, `BOOKING_TEST_SERVICE_ID`, `BOOKING_TEST_RESOURCE_ID` and run:
```bash
cd backend && RUN_BOOKING_INTEGRATION=1 pytest auth_service/tests/test_booking_integration.py -v
```
Expected: PASS (exactly one of 8 concurrent inserts wins).

- [ ] **Step 6: Smoke-test the live widget**

Hit the legacy endpoints (these back the live `/contact` widget): `GET /booking/availability?from=…&to=…` and `GET /booking/slots?date=…` return days/slots; the booking page renders. Confirm no regression.

- [ ] **Step 7: Commit the backup + a note**

```bash
git add backend/migrations/_backup_bookings_2026_06_05.json
git commit -m "chore(booking): snapshot pre-migration bookings + apply multi-tenant migration"
```

---

## Task 12: Second hardening pass (per spec §14 / brief)

- [ ] **Step 1: Run the entire backend suite**

Run: `cd backend && pytest auth_service/tests/ -v`
Expected: all green (integration tests skipped unless the env vars are set).

- [ ] **Step 2: Re-review each module against the spec**

Walk spec §5–§12. Confirm: every `booking_*` table has RLS enabled; the exclusion constraint guards `(resource_id, guard_range)`; tokens are only ever stored hashed; every public route resolves tenant from slug/token (never client-supplied tenant_id); every repo query filters by `tenant_id`; audit rows are written on create/cancel/reschedule. Fix any gap with a TDD cycle.

- [ ] **Step 3: Lint / type check**

Run the repo's configured checks (e.g. `cd backend && ruff check auth_service/ && mypy auth_service/services/booking_*.py auth_service/routers/booking.py` if mypy is configured). Fix findings.

- [ ] **Step 4: Final commit**

```bash
git add -A
git commit -m "chore(booking): phase-1 hardening pass — full suite green"
```

---

## Done criteria (Phase 1)

- Migration applied; 7 rows backfilled into tenant #1; exclusion constraint live; provisioning rows present.
- Domain layer (`booking_tenant`, `booking_availability`, `booking_repo`, `calendar_provider`) unit-tested and green.
- Slug-scoped public API (services/availability/create/manage) + legacy shims; the live widget works unchanged.
- Concurrency test proves no double-book; tenant isolation enforced by per-query `tenant_id` + slug resolution.
- Manage tokens hashed; migrated links resolve.
- Phases 2 (dashboard), 3 (embeddable widget + frontend slug cutover), 4 (per-tenant email branding, i18n, notifications-log idempotency, brand auto-extraction, deploy `pg_cron` reminder job) remain, each its own spec → plan → build cycle.

---

## Post-review hardening (applied after the final adversarial review)

A final code review surfaced items beyond the per-task reviews; these were fixed in this pass:

1. **Reschedule self-collision (correctness).** `busy_guard_intervals_by_resource` now takes `exclude_booking_id`; `manage_reschedule` passes the booking's own id so an overlapping move (with buffers) is not a false 409 against its own current guard.
2. **Reschedule window re-validation.** `manage_reschedule` now re-checks the service `lead_time_min`/`max_advance_days` server-side (client not trusted).
3. **Legacy `note` preserved.** `CreateIn` gained an optional `note`; `_create_core` persists it (`notes`) and renders it in emails; `legacy_create` forwards `body.note`. (Was being dropped after the rewrite.)
4. **Tenant-isolation test added** (`test_booking_slug_router.py::test_tenant_isolation_route_scopes_to_resolved_tenant`) — proves the route only ever queries the slug-resolved tenant id. Integration-test docstring corrected (it covers concurrency only).
5. **DST fall-back test added** (`test_booking_availability.py::test_dst_fall_back_day_uses_post_transition_offset`).
6. **Lint cleanups** — unused imports removed, `COMMON_STARTS` as a dict literal, E402 fixed. `ruff check` clean across all booking files.

Known P1 limitation (tracked to P4): the reminders cron keeps the legacy fixed ~65-min window; per-tenant `reminder_offsets_min` is stored but not yet honored.

Final state: **279 passed, 5 skipped** (the gated DB integration test + 4 pre-existing skips); `ruff` clean. The multi-tenant migration is applied to the DB and validated (7 rows backfilled, exclusion constraint proven to reject overlaps, 3 tokens hashed). Nothing committed (per the no-auto-commit preference).
