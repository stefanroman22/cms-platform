# Multi-Tenant Booking Foundation (Phase 1) — Design Spec

**Date:** 2026-06-05
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design); pending spec review

**Builds on:** `2026-06-03-custom-booking-widget-design.md` and
`2026-06-04-booking-cancel-reschedule-design.md` (the existing single-tenant
"book a call with Stefan" widget — already built, deployed to Supabase, and
**live with 4 confirmed upcoming bookings**, but uncommitted on
`feat/lead-scraper-system`).

**Relationship to the build brief:** This is Phase 1 of the
*Reusable Multi-Tenant Appointment Booking Service* brief. The brief is a
multi-week build; per the brainstorming decision we **decompose it into phases
and design the foundation first**. This spec covers Phase 1 only.

---

## 1. Locked decisions (from brainstorming)

These were settled before writing this spec and are not re-opened here:

1. **Evolve, don't rebuild.** The working single-tenant FastAPI widget becomes
   the multi-tenant foundation; Stefan's site is **tenant #1**. We reuse the
   slot-math core, the email layer, the manage-link flow, and the existing tests.
2. **FastAPI stack** (not Supabase Edge Functions / Deno). The brief's
   Edge-Functions prescription is replaced by the repo's existing FastAPI +
   service-role pattern.
3. **Tenant = project.** `tenant_id` is a FK to `public.projects.id`. No new
   "clients" table.
4. **Full resource-generic foundation.** Phase 1 ships the resources / services /
   hours / exceptions / policies model and a **multi-resource** slot engine.
5. **Google Calendar = adapter seam, off by default.** A `CalendarProvider`
   interface; `calendar_provider = 'none'` for new tenants, `'google'` available
   for tenant #1. Postgres stays the source of truth.
6. **Migration = ALTER in place + backfill** (Option 1). Preserves existing row
   IDs and live manage tokens.
7. **Double-booking = `btree_gist` exclusion** on `(resource_id, guard_range)`,
   replacing the current partial unique index.
8. **Security = app-layer tenant enforcement** (the repo's existing model), not
   the brief's anon→`SECURITY DEFINER`-RPC model. See §4.

## 2. Goal

A reusable, multi-tenant appointment-booking backend that Stefan can plug into
any client website, keyed by `tenant_id` (= a project). End-customers book,
reschedule, and cancel from the client's site through tenant-scoped public
FastAPI endpoints; all booking data lives in Postgres as the single source of
truth. Phase 1 delivers the data model, the slot engine, and the public booking
API — with Stefan's existing widget migrated onto it as tenant #1 and still
working.

## 3. Scope

**In (Phase 1):**
- The `booking_*` data model (§5) + the evolved `bookings` table.
- The `btree_gist` exclusion constraint (§6).
- App-layer multi-tenant isolation (§4).
- The multi-resource, DST-aware slot engine (§7).
- Tenant-scoped public booking endpoints: services, availability, create,
  manage (get / cancel / reschedule), with hashed manage tokens (§8).
- The `CalendarProvider` adapter seam (§9).
- The ALTER-in-place migration + tenant-#1 backfill of the 7 existing rows (§10).
- Config changes (§11) and the Phase-1 automated test slice (§12).

**Out (later phases — not designed here):**
- **P2:** CMS dashboard "Bookings" section (overview/stats with recharts,
  appointments, services, resources, hours, policies, branding, embed).
- **P3:** the embeddable widget — iframe `embed.js` snippet + React package —
  and generalising the manage page for arbitrary client sites.
- **P4:** per-tenant email branding, i18n/localisation, `booking_notifications_log`
  + idempotency keys, brand auto-extraction, deploying the `pg_cron` reminder
  job, **honoring per-tenant `reminder_offsets_min`** (P1's cron keeps the legacy
  fixed ~1h window; the column is stored but not yet read), Google-Maps hours import.

**Future seams (built as seams, not features):** payments/deposits (a hook point
in create + a `party_size` column already present), restaurant tables
(`resource` type + `capacity` + a future `booking_type`), 3D table map
(additive resource attributes), external calendar sync (the §9 adapter),
SMS reminders (a `channel` column when the notifications log lands in P4).

## 4. Tenancy & security model

**Deliberate, repo-consistent deviation from the brief.** The brief prescribes
the anon role with no table grants and public booking through
`SECURITY DEFINER` RPCs. This repo does not use Supabase Auth JWTs or the anon
key anywhere — it uses hand-rolled session cookies and a **service-role Supabase
client with authorization enforced in FastAPI** (confirmed across `projects`,
`content_entries`, etc.). Phase 1 matches that pattern:

- **Every `booking_*` table:** RLS **enabled, no anon/authenticated policies** →
  reachable only by the service-role client. The browser never touches the DB.
- **Public booking** flows through **public FastAPI routes keyed by
  `public_slug`.** The route resolves `tenant_id` from the slug server-side; the
  client never sends a tenant id and therefore cannot target another tenant.
- **Owner/staff** access (dashboard, P2) will flow through authenticated FastAPI
  routes that resolve the caller's tenant from their session and check project
  ownership in app code (the existing pattern).
- **The brief's security intent is fully met:** anon has zero DB access;
  cross-tenant isolation is enforced in FastAPI and **proven by an automated
  tenant-A-vs-tenant-B isolation test** (§12) that asserts no endpoint or token
  path lets one tenant read or mutate another's rows.

## 5. Data model

All new tables are namespaced `booking_*`, carry `tenant_id uuid not null
references public.projects(id) on delete cascade`, and have RLS enabled with no
public policies. UUID PKs via `gen_random_uuid()`; `created_at`/`updated_at`
`timestamptz`. The main table keeps the name `bookings` (matches the brief).

### 5.1 `booking_settings` — one row per tenant (config + branding)
- `tenant_id` (PK, FK → projects.id)
- `public_slug` text **unique not null** — the public addressing key (defaults to
  the project slug; tenant #1 = `roman-technologies-website`)
- `timezone` text not null (IANA), `locale` text not null default `'en'`
- `business_name`, `logo_url`, `primary_color`, `accent_color`,
  `email_from_name` (branding — consumed in P2/P4; stored now)
- `owner_notification_email` text not null
- `slot_granularity_min` int not null default 15
- `reminders_enabled` bool not null default true
- `reminder_offsets_min` int[] not null default `'{1440,120}'`
- `calendar_provider` text not null default `'none'` (`'none' | 'google'`) — the
  §9 seam
- `is_active` bool not null default true, `created_at`, `updated_at`

### 5.2 `booking_resources` — bookable unit (staff / chair / bay / generic)
- `id`, `tenant_id`, `name`, `type` (`staff|room|equipment|generic`),
  `capacity` int not null default 1 *(reserved; the §6 constraint assumes 1)*,
  `is_active` bool default true, `sort_order` int default 0

### 5.3 `booking_services` — what can be booked
- `id`, `tenant_id`, `name`, `description`, `color`
- `duration_min` int not null
- `buffer_before_min` int not null default 0, `buffer_after_min` int not null
  default 0
- `lead_time_min` int not null default 0 (minimum notice)
- `max_advance_days` int not null default 60
- `is_active` bool default true, `sort_order` int default 0

### 5.4 `booking_service_resources` — m:n eligibility
- `(service_id, resource_id)` composite PK, `tenant_id`

### 5.5 `booking_hours` — recurring weekly opening hours
- `id`, `tenant_id`, `resource_id` **nullable** (null → whole business),
  `weekday` int (0–6, **0 = Sunday**; see note), `start_time` time, `end_time` time
- Multiple rows per weekday allowed (split shifts). Times are **tenant-local**;
  converted to UTC at slot-generation time.
- **Weekday convention note:** the existing config uses ISO weekday (Mon=1..Sun=7).
  `booking_hours.weekday` standardises on **0–6 with 0=Sunday** (Postgres
  `extract(dow)` convention) so DB-side queries are natural; the migration maps
  the ISO config accordingly. The slot engine uses one convention end-to-end.

### 5.6 `booking_exceptions` — holidays / one-off overrides
- `id`, `tenant_id`, `resource_id` nullable, `date` date, `is_closed` bool,
  `start_time` time nullable, `end_time` time nullable (custom hours replace)

### 5.7 `booking_policies` — reschedule/cancel rules (per tenant, optional per service)
- `id`, `tenant_id`, `service_id` **nullable** (null = tenant default; non-null =
  override)
- `allow_reschedule` bool default true, `reschedule_window_hours` int default 24,
  `max_reschedules` int default 2
- `allow_cancel` bool default true, `cancellation_window_hours` int default 24
- `policy_text` text (shown to the customer; localised in P4)

### 5.8 `booking_customers`
- `id`, `tenant_id`, `name`, `email`, `phone` nullable, `locale`, `timezone`,
  `created_at`
- **Unique `(tenant_id, email)`** — dedupes repeat customers per tenant.

### 5.9 `bookings` (evolved from the existing table)
Existing columns kept: `id`, `start_utc`, `end_utc`, `status`,
`reminder_sent_at`, `created_at`, `google_event_id`, `reschedule_count`.
Columns **added**:
- `tenant_id` not null (FK → projects.id)
- `service_id` not null (FK → booking_services.id)
- `resource_id` not null (FK → booking_resources.id) — the assigned concrete
  resource (required for the exclusion constraint)
- `customer_id` not null (FK → booking_customers.id)
- `guard_range tstzrange not null` — `[start − buffer_before, end + buffer_after)`,
  used by the exclusion constraint and by slot subtraction (§6, §7). **Implemented**
  as two scalar columns `guard_start_utc`/`guard_end_utc` (written by the app) plus a
  `generated always as (tstzrange(guard_start_utc, guard_end_utc, '[)')) stored`
  column — same semantics, friendlier reads for PostgREST.
- `party_size` int not null default 1 *(reserved for future)*
- `manage_token_hash` text — SHA-256 of the opaque token (replaces plaintext
  `manage_token`)
- `source` text not null default `'widget'` (`widget|dashboard|api`)
- `notes` text, `cancel_reason` text
- `updated_at` timestamptz, `cancelled_at` timestamptz

Columns **dropped** after backfill: `name`, `email`, `note`, `visitor_timezone`
(moved to `booking_customers`), `manage_token` (replaced by the hash).

`status` enum semantics widen to `pending|confirmed|cancelled|completed|no_show`
(text + a CHECK; default `confirmed`).

**Display vs. collision (the approved two-range approach):** `start_utc`/`end_utc`
remain the canonical **customer-facing** instants (kept to minimise churn in the
slot engine, emails, and reminders, all of which already read them).
`guard_range` is the **buffer-expanded collision interval** — the only thing the
exclusion constraint and the slot-subtraction step look at. For tenant #1
(buffers = 0) `guard_range = [start_utc, end_utc)`.

### 5.10 `booking_audit_log` — append-only action trail
- `id`, `tenant_id`, `booking_id`, `action`, `actor` (`owner|customer|system`),
  `payload` jsonb, `created_at`

*(`booking_notifications_log` is deferred to P4, where email-idempotency keys
are introduced.)*

## 6. Double-booking prevention (database level)

```sql
create extension if not exists btree_gist;

alter table public.bookings
  add constraint bookings_no_overlap
  exclude using gist (resource_id with =, guard_range with &&)
  where (status in ('pending','confirmed'));
```

- This **replaces** `bookings_confirmed_start_uniq` (which only guards one global
  resource on a fixed slot grid). The new constraint guards per resource, for
  arbitrary durations, and is buffer-aware (via `guard_range`).
- The create/reschedule endpoint runs availability-check + insert in **one
  transaction**. On a `23P01` exclusion violation (race lost), it catches the
  error, tries the next free eligible resource if one exists (§7.6), and
  otherwise returns a clean **409 "that time was just taken"**; the widget
  re-fetches slots.
- A concurrency test (§12) fires N simultaneous bookings at one slot/resource and
  asserts exactly one succeeds.
- **Capacity > 1** (future tables/seats) is out of scope; the constraint assumes
  `capacity = 1`. Supporting capacity later needs a different mechanism (noted as
  a future seam, not built now).

## 7. Slot engine (multi-resource, DST-aware)

Evolve `services/booking_availability.py` — keep its pure, no-I/O,
`zoneinfo`-based DST core; generalise from one global resource to N eligible
resources. Inputs are plain data (hours, exceptions, existing `guard_range`s per
resource, service duration/buffers/lead/advance, `now`, tenant tz); output is a
list of available UTC slot starts. Per service, per day in the requested range:

1. Resolve tenant tz. Build the day's open intervals from `booking_hours`
   (matching `weekday`) in tenant-local time, then convert to UTC `tstzrange`
   — DST-aware (spring-forward gaps collapse, fall-back overlaps handled).
2. Subtract `booking_exceptions` (closed → zero out the day; custom hours →
   replace).
3. **Per eligible resource**, subtract existing bookings' `guard_range`s
   (status in `pending|confirmed`).
4. Walk each resource's remaining free intervals in `slot_granularity_min` steps,
   emitting a start `s` only if `s + duration_min ≤ interval_end`.
5. Filter `s ≥ now + lead_time_min` and `s ≤ now + max_advance_days`.
6. **A slot is offered if ≥ 1 eligible resource is free at `s`.** The concrete
   `resource_id` is assigned at **booking time** (least-loaded among free
   eligible resources). If the chosen resource loses the exclusion race, fall
   through to the next free eligible resource before returning 409.

Returns UTC ISO starts. The widget renders them in the customer's timezone
(unchanged from today).

## 8. Public API surface (FastAPI, slug-scoped)

Evolve the existing `routers/booking.py` endpoints to be tenant-scoped. All
resolve `tenant_id` from `public_slug` (404 on unknown/inactive tenant) and
apply the existing honeypot + IP rate-limits.

- `GET /booking/{slug}/services` → active services (name, duration, policy
  summary).
- `GET /booking/{slug}/availability?service_id=&from=&to=&tz=` → bookable days /
  slots (§7).
- `POST /booking/{slug}` → body `{ service_id, resource_id?, start_utc,
  customer:{name,email,phone?,locale?,tz} }`. Validates lead/advance/availability,
  upserts the customer (`(tenant_id,email)`), assigns a resource, computes
  `guard_range`, inserts atomically (§6), generates an opaque manage token
  (≥32 bytes base64url) and stores **only its SHA-256 hash**, fires confirmation
  emails best-effort, returns `{ booking_id, manage_url }`.
- `POST /booking/manage/{token}` → booking details for the manage page (token
  hashed, then looked up by `manage_token_hash`).
- `POST /booking/manage/{token}/cancel` → enforces policy windows server-side;
  sets `cancelled`; calendar adapter `delete`; emails both parties.
- `POST /booking/manage/{token}/reschedule` → enforces policy + availability;
  updates; increments `reschedule_count`; **rotates the token** (new hash, resend
  manage link); calendar adapter `update`; emails both parties.

**Manage-token migration:** the 3 existing live tokens are hashed in place during
the migration (§10), so already-sent manage links keep resolving; the plaintext
column is then dropped. Tokens are rejected gracefully for past/cancelled
bookings.

All policy and availability checks are **server-side**; the client is never
trusted. Every state change writes a `booking_audit_log` row.

## 9. Calendar adapter seam

Define a `CalendarProvider` protocol — `create_event`, `update_event`,
`delete_event`, `list_busy` — and a `NoopCalendarProvider` (default). The
existing Google code becomes `GoogleCalendarProvider`. The active provider is
selected per tenant from `booking_settings.calendar_provider`
(`'none'` → noop; `'google'` → Google, using the existing `GOOGLE_*` env for
tenant #1). The slot engine calls `list_busy` only when the provider is non-noop;
create/cancel/reschedule call the provider best-effort (failures logged, DB
remains authoritative). **No new calendar feature is built** — only the seam,
plus wiring the existing Google sync behind it for tenant #1.

## 10. Migration / evolution strategy (ALTER in place + backfill)

One migration `backend/migrations/2026_06_05_booking_multitenant.sql`, applied
via Supabase MCP (per project convention). Steps:

1. `create extension if not exists btree_gist;`
2. Create the 9 new `booking_*` tables (§5.1–5.8, 5.10) with RLS enabled, no
   public policies.
3. **Provision tenant #1** (project `roman-technologies-website`,
   `a7fccf9f-35ba-4655-baba-6744cab738dc`):
   - `booking_settings` from `config.py` — timezone `Europe/Berlin`, locale `en`,
     `owner_notification_email = stefanromanpers@gmail.com`,
     `public_slug = 'roman-technologies-website'`, `calendar_provider` =
     `'google'` if `GOOGLE_*` configured else `'none'`,
     `reminder_offsets_min = '{60}'` (matches the current ~1h reminder).
   - one `booking_resources` row (`name='Stefan'`, type `staff`).
   - one `booking_services` row (`name='Consultation'`, `duration_min=45`,
     buffers 0, `lead_time_min=120`, `max_advance_days=120`) + its
     `booking_service_resources` link.
   - `booking_hours` rows from `BOOKING_HOURS` (`1=9-20,…,7=12-17`), mapped from
     ISO weekday to the 0–6/Sun=0 convention.
   - default `booking_policies` row (reschedule window 12h to match current,
     `max_reschedules=2`; cancel window 24h).
4. **Alter `bookings`**: add the §5.9 columns (initially nullable where needed),
   widen the `status` CHECK.
5. **Backfill the 7 rows**: set `tenant_id`, `resource_id`, `service_id` to
   tenant #1's; build `guard_range = tstzrange(start_utc, end_utc, '[)')`;
   extract `(name,email,visitor_timezone)` into `booking_customers` (2 distinct
   customers) and set `customer_id`; copy `note → notes`; set
   `manage_token_hash = encode(digest(manage_token,'sha256'),'hex')` for the 3
   rows that have a token (the other 4 stay null); `source='widget'`.
6. **Tighten**: set the added FK columns `not null`; drop the old columns
   (`name,email,note,visitor_timezone,manage_token`); drop
   `bookings_confirmed_start_uniq`; add `bookings_no_overlap` (§6).
7. Leave the data backfill idempotent/guarded (`where tenant_id is null`) so a
   re-run is safe.

The existing frontend widget is repointed at tenant #1's slug (the booking
components are themselves uncommitted, so this is part of the same change set).

## 11. Config changes (`core/config.py`)

The per-tenant values (timezone, hours, slot/buffer/notice/horizon, host email,
meeting URL, max-reschedules) move **into `booking_settings`** as the source of
truth; the `BOOKING_*` env vars are retained only as the **seed for the
tenant-#1 backfill** and as fallback defaults. New global infra config:
`BOOKING_MANAGE_BASE_URL` (defaults to `BOOKING_PUBLIC_BASE_URL`) for building
`/manage/{token}` links. `GOOGLE_*` and `BOOKING_CRON_SECRET` are unchanged. No
new Python dependencies (hashing via stdlib `hashlib`; DB extension `pgcrypto`
or `digest` available in Postgres for the backfill).

## 12. Testing (Phase-1 slice of the brief's §13 matrix)

Automated, mostly pure-function + FastAPI `TestClient`, extending the existing
booking tests. Manual-only checks are not acceptable.

- **DST:** booking across a spring-forward gap and a fall-back overlap; tenant
  tz ≠ customer tz; correct UTC math both directions.
- **Concurrency:** N simultaneous bookings on one slot/resource → exactly one
  succeeds; 409 path clean and the next-free-resource fallthrough works. Run
  against the real exclusion constraint.
- **Slot math:** lead-time boundary; max-advance boundary; buffers (no
  off-by-one gaps, via `guard_range`); back-to-back bookings; split-shift hours;
  closed-day / holiday / custom-hours exceptions.
- **Multi-resource:** slot offered if ≥1 eligible resource free; correct
  least-loaded assignment; no cross-resource double-book.
- **Reschedule/cancel:** into an unavailable slot (rejected); outside the policy
  window (rejected); exceeding `max_reschedules` (rejected); token rotation on
  reschedule.
- **Isolation (mandatory):** tenant A cannot read or mutate tenant B's rows via
  any endpoint or token path.
- **Manage token:** invalid / tampered / reused-after-cancel / past booking →
  graceful reject; hashed-token lookup; a **migrated** token (one of the 3 live
  ones) still resolves.
- **Backfill:** an automated check (or a documented one-shot verification) that
  after migration the 4 confirmed upcoming bookings are intact, linked to tenant
  #1, with valid `guard_range` and customer rows.

## 13. Conventions honored

`zoneinfo` (no new date lib); supabase-py service-role client; Supabase-MCP
migration path (`YYYY_MM_DD_*.sql` in `backend/migrations/`); the existing
`limiter` + honeypot + E2E email guard; the issue-resolved email header/footer
helper; surgical changes; **no auto-commit** (per Stefan's standing preference —
this doc and all code are committed only when Stefan says so).
