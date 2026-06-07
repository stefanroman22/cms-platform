# Bookings Dashboard — Config & Provisioning (Phase 2a) — Design Spec

**Date:** 2026-06-05
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design)

**Builds on:** the multi-tenant booking foundation
(`2026-06-05-multi-tenant-booking-foundation-design.md`, Phase 1 — schema +
slot engine + public API, migrated and live). This is **Phase 2a** of the
dashboard work; Appointments (2b) and Overview/stats (2c) follow as their own
spec → plan → build cycles.

## Goal

Let a project owner (the client) self-manage their booking configuration from
the existing CMS dashboard, and let Stefan (admin) **enable** bookings for a
client in one click — so onboarding a new tenant needs no SQL. Phase 2a delivers
the "Bookings" dashboard section, its gating, the admin enable/provisioning
action, and the five **config** sub-pages (Settings, Services, Resources, Hours,
Policies — Hours includes closed-date Exceptions), backed by new
**authenticated owner-facing** FastAPI endpoints (Phase 1 only built public
slug routes).

## Locked decisions (from brainstorming)

1. **Decompose Phase 2**; build **2a (config + provisioning)** first.
2. **Owner manages, admin enables.** The project owner sees and manages the
   Bookings section once it's enabled; only an admin can enable it.
3. **Provisioned = enabled.** A `booking_settings` row existing for the project
   means bookings are enabled. No new feature-flag column.
4. **No new DB migration** — 2a reuses the Phase-1 schema; "enable" inserts rows
   at runtime.

## Scope

**In (2a):**
- New authenticated router for owner config endpoints (§API).
- The admin **enable/provision** action (idempotent).
- Dashboard "Bookings" section + capability-based gating + inner tab strip.
- Five config UIs: Settings, Services, Resources, Hours (+ Exceptions), Policies.
- Automated tests (backend endpoint + ownership + provisioning; frontend
  typecheck/build + key component tests).

**Out (later):** Appointments management (2b); Overview/stats charts (2c); the
Embed snippet page (ships with the P3 widget); per-tenant reminder-offset
honoring + email branding/i18n (P4).

## Tenancy & auth model

Owner endpoints use the existing dashboard auth: session cookie `sid` →
`require_user(request)` → `require_project_access(slug, user)` which resolves the
project row (404 if missing) and enforces `project.user_id == user.id or
user.is_admin` (403 otherwise). The resolved `project.id` **is** the booking
`tenant_id`. Every query is scoped to that tenant_id. The `enable` endpoint
additionally requires admin (`admin_user_via_bearer_or_sid`). RLS stays
enabled-no-policy; access is enforced in FastAPI (the repo's established model).

## API — `backend/auth_service/routers/booking_admin.py` (prefix `/projects/{slug}/bookings`)

Reuses `services/booking_repo.py` (extended with owner CRUD helpers) and
`services/booking_tenant.py`. JSON in/out; Pydantic request models; errors as
`{detail}` with 4xx codes (matches existing routers).

- `GET /settings` → the settings row as `{enabled: true, ...fields}`, or
  `{enabled: false}` when no row exists. (Drives section gating + the Settings
  form.)
- `POST /enable` *(admin only)* → idempotent. If no `booking_settings` row:
  insert one (`public_slug` = project slug; `timezone` default `'Europe/Berlin'`;
  `locale` `'en'`; `owner_notification_email` = the project owner's email from
  `users`; `business_name` = project name; `calendar_provider 'none'`), plus a
  default resource (`'Staff'`, type `staff`), a default service
  (`'Consultation'`, 30 min), its service-resource link, Mon–Fri 09:00–17:00
  `booking_hours` (business-level), and a default `booking_policies` row. Returns
  the new settings. Re-running is a no-op (guards on existing rows).
- `PATCH /settings` → update `timezone`, `locale`, `business_name`, `logo_url`,
  `primary_color`, `accent_color`, `email_from_name`, `owner_notification_email`,
  `meeting_url`, `slot_granularity_min`, `reminders_enabled`,
  `reminder_offsets_min`, `calendar_provider`, `public_slug`. `public_slug` is
  validated URL-safe + globally unique (409 on clash).
- `GET /services` · `POST /services` · `PATCH /services/{id}` · `DELETE
  /services/{id}`. Create/patch accept the service fields **plus** `resource_ids:
  string[]` → the endpoint replaces that service's `booking_service_resources`
  rows accordingly. Delete is a hard delete (no bookings reference services by
  FK with cascade concerns: `bookings.service_id` references services; if a
  service has bookings, return 409 "service has bookings" rather than orphan —
  prefer setting `is_active=false`; **delete only when no bookings reference it**).
- `GET /resources` · `POST /resources` · `PATCH /resources/{id}` · `DELETE
  /resources/{id}` — same delete guard (block if referenced by bookings;
  otherwise allow; deactivate via `is_active`).
- `GET /hours` → all `booking_hours` rows for the tenant. `PUT /hours` → body is
  the full weekly set `[{resource_id?, weekday, start_time, end_time}]`; replaces
  all rows for the tenant in one transaction-like operation (delete-then-insert
  scoped to tenant). Validates `start_time < end_time`, weekday 0–6.
- `GET /exceptions` · `POST /exceptions` · `DELETE /exceptions/{id}` — closed
  dates / custom-hours overrides.
- `GET /policies` → tenant default + any per-service overrides. `PATCH
  /policies` → upsert the tenant default (and optionally a `service_id`
  override) with the window/limit/toggle/text fields.

All mounted in `main.py` alongside the existing booking router.

## Frontend — dashboard section

**Gating.** Extend `sectionConfig.ts`: add
`{ key: "bookings", label: "Bookings", icon: Calendar }` and a capability
predicate so it's visible when `bookingEnabled || isAdmin` (not `adminOnly`).
`visibleSections` gains a `caps: { bookingEnabled: boolean }` argument; the
dashboard page (`app/dashboard/[projectSlug]/page.tsx`) fetches
`bookingEnabled` from `GET …/bookings/settings` (a small `useQuery`) and passes
it in, plus renders `activeView === "bookings" && <BookingsSection … />`.

**`components/dashboard/booking/BookingsSection.tsx`** (props `projectSlug`,
`isAdmin`):
- Loads `GET …/settings`. If `enabled === false`: render an **EnableBookings**
  panel — admins see an "Enable bookings" button (`POST …/enable`, then
  re-fetch); non-admins won't reach this (section hidden), but render a neutral
  "Bookings aren't enabled for this project yet" message as a safety net.
- If enabled: an **inner tab strip** — Settings · Services · Resources · Hours ·
  Policies — switching focused child components (URL or local state; local
  state is fine for an inner strip).

**Child components** (each one file, one responsibility):
- `BookingSettingsForm.tsx` — mirrors `ProjectSettingsSection` (draft state,
  PATCH, success/error banner). Branding fields + tz/locale + slug + reminders +
  calendar provider + meeting URL.
- `ServicesManager.tsx` + `ServiceFormDrawer.tsx` — list (from `GET /services`)
  + add/edit drawer (mirrors `LeadDetailDrawer` + a `useBookingResource` patch
  hook), with the eligible-resources multiselect.
- `ResourcesManager.tsx` + `ResourceFormDrawer.tsx` — list + add/edit drawer.
- `HoursEditor.tsx` — a weekly grid (7 rows; add/remove intervals per day;
  business-level by default) + a "Closed dates" sub-panel for exceptions.
  Saves via `PUT /hours` (full replace) and `POST/DELETE /exceptions`.
- `PoliciesForm.tsx` — reschedule/cancel windows + limits + toggles + policy
  text, with a live preview of the customer-facing policy text.

**Conventions:** all use `dashboardInputCn` / `dashboardFieldLabelCn` /
`dashboardSectionCardCn` / `dashboardErrorBannerCn` / `dashboardSuccessBannerCn`
from `lib/styles.ts`; data via the existing `useQuery` + `cache` helper; all
`fetch('/api/projects/{slug}/bookings/…', { credentials: 'include' })`; buttons
get `cursor-pointer` (global rule); `motion/react` for the drawer; reduced-motion
respected. Fully responsive (the dashboard shell already is).

## Error & edge handling

- Unknown/inaccessible project → 404/403 from `require_project_access`; the UI
  shows the standard error banner.
- `enable` on an already-enabled project → no-op, returns current settings.
- `public_slug` clash → 409, surfaced inline on the Settings form.
- Deleting a service/resource still referenced by bookings → 409 with a clear
  message; the UI suggests deactivating (`is_active=false`) instead.
- Empty states (no services/resources/hours yet) render friendly prompts.
- `PUT /hours` validates each interval; an invalid interval → 422, inline error.

## Testing

**Backend** (`tests/test_booking_admin_router.py`): owner can read/write own
project's config; a different owner gets 403 on someone else's project
(isolation); non-admin gets 403 on `enable`; `enable` provisions the default set
and is idempotent on re-run; services/resources/hours/policies CRUD round-trips;
`public_slug` uniqueness 409; delete-guard 409 when referenced. Mock the
Supabase client per the existing test style; reuse `require_project_access`
seams.

**Frontend:** `npm run typecheck` + `npm run build` clean. Component tests
(where the repo has them) for: the EnableBookings CTA (admin sees it,
calls `/enable`), the Settings form PATCH round-trip, and a Services add/edit
round-trip — fetch mocked.

## Conventions honored

Existing dashboard section pattern (`sectionConfig` + page switch +
`SectionRail`/`SectionPanel`); `require_project_access` ownership guard;
`/api/[...path]` proxy with `sid` cookie; `useQuery`/`cache`; `lib/styles.ts`
primitives; `recharts` reserved for 2c; supabase-py service-role client with
app-layer authz; surgical changes; **no auto-commit**; no new DB migration.
