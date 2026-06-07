# CMS Connector × Booking Service — Auto-Integration Design

**Date:** 2026-06-06
**Status:** Approved (design), pending implementation plan
**Area:** `agents/CMS Connector - Website/` (scan/prompts/integration/testing/LEARNINGS) · `backend/auth_service/` booking module (two shared fixes) · `frontend/src/components/booking/` (widget color fix) · generated client repos (`lib/booking.ts` + UI wiring)

## Goal

When the CMS Connector agent imports a client website, if the site's design/source contains a **booking / scheduling** experience (or a scheduling-type form), the connector should — after a human-review gate — **provision the reusable booking backend for that project and wire the client's own bespoke booking UI to it**, so booking, rescheduling, cancelling, and confirmation/reminder emails work automatically, branded to that client.

The booking service is treated as a **headless backend**. The client keeps whatever booking UI its design specifies (custom date picker, service list, customer form, themed to its own site); the connector connects that UI to the booking API. The connector does **not** impose a fixed widget.

## Background: the booking module (as analyzed 2026-06-06)

Multi-tenant, **tenant = project**, addressed by a globally-unique `public_slug`. All per-tenant config is one `booking_settings` row + satellite tables (`booking_services`, `booking_resources`, `booking_service_resources` link, `booking_hours`, `booking_exceptions`, `booking_policies`). RLS is enabled with no policies — authorization is app-layer (every repo call is tenant-scoped).

**Public HTTP contract** (slug-scoped, anonymous — what a bespoke client UI calls):
- `GET /booking/{slug}/config` → `{public_slug, business_name, primary_color, accent_color, logo_url, locale}`
- `GET /booking/{slug}/services` → `{services:[{id,name,duration_min}]}`
- `GET /booking/{slug}/availability?service_id=&from=YYYY-MM-DD&to=YYYY-MM-DD` → `{days:[{date,slots:[{start_utc}]}]}`
- `POST /booking/{slug}` → body `{service_id, resource_id?, start_utc, customer:{name,email,phone?,tz?,locale?}, note?, website}` (`website` = honeypot, must be empty). Returns `{success, booking_id, manage_url, start, end}`. Rate-limited 5/h/IP; DB gist-exclusion → HTTP 409 on double-book.
- `GET /booking/manage/{token}` → booking detail + `can_cancel`/`can_reschedule`
- `POST /booking/manage/{token}/reschedule` → `{slot_start}` (rotates token); `POST /booking/manage/{token}/cancel`

**Admin/provisioning contract** (owner-or-admin, project-scoped):
- `POST /projects/{slug}/bookings/enable` — **idempotent provision**; seeds a complete working config (settings + one resource + one service + the service↔resource link + Mon–Fri 09–17 hours + default policy).
- `PATCH /projects/{slug}/bookings/settings` — set `business_name, public_slug, timezone, locale, owner_notification_email, email_from_name, primary_color, accent_color, logo_url, meeting_url, slot_granularity_min, reminders_enabled, reminder_offsets_min, calendar_provider, email_copy`.
- Services CRUD `…/bookings/services`; Resources CRUD `…/bookings/resources`; `PUT …/bookings/hours` (full replace); Policies `PATCH …/bookings/policies`; `POST …/bookings/logo`; `GET …/bookings/email-template`, `POST …/bookings/email-preview`.

**Reminders**: a global `pg_cron` job POSTs `/booking/cron/reminders` (header `X-Cron-Secret`); per-tenant `reminders_enabled` + `reminder_offsets_min`. Optional, already-deployed infra.

**Critical "no slots" pitfalls** the connector must avoid: missing `booking_service_resources` link → zero availability; no `booking_hours` rows → no windows; `is_active=false`; timezone mismatch. (`enable` seeds all of these correctly — provisioning must go through `enable`, not a bare settings insert.)

**Limitations relevant here:**
- **The iframe widget ignores per-tenant colors** — `BookingCalendar.tsx` sets `--booking-primary`/`--booking-accent` CSS vars but nothing consumes them (the widget renders the global `--color-accent` `#c9a961`). Per-tenant colors currently show only in **emails**.
- **Emails hardcode "Stefan"** — `booking_i18n.STRINGS` (confirm/reminder/cancel/reschedule subjects + subtext) and the calendar-event titles in `booking_email.py` / `booking_manage_email.py` (`Call with Stefan @ {business_name}`).
- From **address** is global (`noreply@roman-technologies.dev`); only From display name is per-tenant. Widget + email UI strings are **English-only**. Calendar creds are global → clients use `calendar_provider='none'`. Falls back to **Roman Technologies branding** if business_name+logo+accent all empty.

## Key decisions (settled in brainstorming)

1. **Headless**: connector provisions the backend + wires the client's bespoke UI via a generated `lib/booking.ts`; no imposed UI. (Optional iframe-embed fallback only when a site shows booking intent but has no usable UI.)
2. **Fix the two module limitations** so "colors match theme" and "company name in template" genuinely hold: (a) de-hardcode "Stefan" in emails + calendar titles, (b) make the iframe widget consume the per-tenant CSS color vars.
3. **Ownership = Stefan** (project owner + admin). **Destination email** = the client email you provide if given, else `stefanromanpers@gmail.com`.
4. **Centralized manage page**: confirmation emails link to the CMS-hosted `{manage_base_url}/manage/{token}` (works for any tenant); client sites need no manage UI, though `lib/booking.ts` exposes manage/reschedule/cancel for a custom one later.
5. **One pass**: the shared booking-module fixes and the connector-agent extension are implemented together.
6. **Human-review gate**: a "Booking Service" section in the Phase-3 Markdown report shows the full proposed config for you to edit before Phase-4 writes anything.
7. **Widened self-improvement**: LEARNINGS captures booking feedback **and** both positive and negative feedback as durable cross-project rules.

## Architecture

```
CMS Connector run on a client site
  Phase 2 SCAN ── detect booking intent + extract config from design/source
        │            (business_name, theme colors, services, staff/resources, hours, locale, tz)
        ▼
  Phase 3 REVIEW ── "Booking Service" section in cms-integration-report.md  ← Stefan edits
        │
        ▼
  Phase 4 INTEGRATE
     ├─ Backend: POST .../bookings/enable → PATCH settings + replace services/resources/hours
     │            + colors + logo + email_copy; owner_notification_email = client-or-Stefan
     ├─ Client repo: generate lib/booking.ts (headless API client) + booking config (slug + BOOKING_API_BASE)
     │            + WIRE the design's booking UI (service picker / date-time / customer form) to it
     └─ Env: NEXT_PUBLIC_/VITE_/PUBLIC_ BOOKING_API_BASE per framework
        │
        ▼
  Phase 5 TEST ── smoke the public flow (services→availability→book→manage→reschedule→cancel),
                  email-preview render, reminders cron; client build/render check
        │
        ▼
  Phase 6 ── LEARNINGS updated (booking rules + positive/negative feedback loop)

Shared module fixes (one pass): de-hardcode "Stefan" (emails+calendar titles); widget consumes color vars.
```

## 1. Detection (Phase 2 scan)

Flag a **booking service** when the design/source shows **scheduling intent**, e.g.:
- a calendar / date-time slot selector, or an "appointment / book a call / book a table / reserve / schedule" flow;
- a services-with-durations list combined with staff/resources and/or opening hours;
- an existing booking widget/component.

A plain **contact form** (no scheduling) stays the existing `email_config` → Resend path; booking is only for scheduling. When ambiguous, the agent proposes booking in the report and lets the human gate decide.

Extract from the design/source (demo values acceptable — Stefan edits in the report):
- `business_name`, brand **colors** (→ `accent_color` primary, `primary_color` secondary), logo;
- **services**: name + `duration_min` (+ optional description/price-as-text);
- **resources/staff**: names (mapped to `booking_resources`, `type='staff'`);
- **opening hours** (→ `booking_hours`, weekday `0=Sun..6=Sat`, local times);
- `locale`, `timezone` (from the site's market/locale; default `Europe/Berlin`/`en`).

## 2. Manifest + report additions

The Phase-2 manifest gains a top-level optional `booking` block:
```jsonc
"booking": {
  "detected": true,
  "public_slug": "<project-slug>",
  "business_name": "...",
  "accent_color": "#...", "primary_color": "#...", "logo_url": "...",
  "locale": "en", "timezone": "Europe/Berlin",
  "destination_email": "<client-or-stefan>",
  "calendar_provider": "none",
  "reminders": { "enabled": true, "offsets_min": [1440, 120] },
  "services":  [{ "name": "Consultation", "duration_min": 30 }],
  "resources": [{ "name": "Staff", "type": "staff" }],
  "hours":     [{ "weekday": 1, "start_time": "09:00", "end_time": "17:00" }],
  "ui_wiring": { "components": ["<paths of the client's booking UI to wire>"], "fallback_embed": false }
}
```

**Phase-3 report — "## Booking Service" section** renders this block human-readably: detected? proposed slug, business name, colors (swatches), the services table, resources/staff, the weekly hours grid, destination email, locale/timezone, `calendar=none`, reminder offsets, the client UI components to be wired (or "iframe fallback"), and the public API contract the UI will use. Stefan edits any of it before Phase 4. (Mirrors the existing report's per-section editing.)

## 3. Provisioning + wiring (Phase 4)

**Backend (admin API, in order — `enable` first so the link/hours/policy are seeded):**
1. `POST /projects/{slug}/bookings/enable` (idempotent).
2. `PATCH /projects/{slug}/bookings/settings`: `public_slug` (= project slug), `business_name`, `timezone`, `locale`, `email_from_name` (= business_name), `owner_notification_email` (see below), `accent_color`, `primary_color`, `calendar_provider:'none'`, `reminders_enabled`, `reminder_offsets_min`, and `email_copy` overrides (company-centric subjects/subtext).
3. Replace **services** (delete the seeded `Consultation`, create the design's services), **resources/staff**, **hours** (`PUT`), ensuring every service is linked to ≥1 resource (the API links on create; verify). `POST …/bookings/logo` if a logo asset exists.
4. Policies: keep defaults unless the design implies otherwise.

**Destination email**: `owner_notification_email` = the client email Stefan provides for this project if given, else `stefanromanpers@gmail.com`. (Project ownership stays Stefan; `enable` defaults the email to the project owner = Stefan, then this PATCH overrides it.)

**Company name in emails**: `business_name` + `email_from_name` drive header/footer/from-name; `email_copy` overrides the editable subject/subtext strings to be company-centric. (The non-overridable hardcodes are handled by module fix #1 below.)

**Client repo wiring:**
- Generate **`lib/booking.ts`** — a typed headless client (booking analog of `cms.ts`): `getConfig()`, `getServices()`, `getAvailability(serviceId, from, to)`, `createBooking({service_id, start_utc, customer, note})`, `getManage(token)`, `reschedule(token, slot_start)`, `cancel(token)` — all against `${BOOKING_API_BASE}/booking/{slug}/…`. The honeypot `website:""` is sent automatically.
- Generate booking config (the `public_slug` + the `BOOKING_API_BASE` env-var name per framework: `NEXT_PUBLIC_BOOKING_API_BASE` / `VITE_BOOKING_API_BASE` / `PUBLIC_BOOKING_API_BASE`).
- **Wire the design's booking UI** (service picker → `getServices`, date/time selector → `getAvailability`, customer form submit → `createBooking`, success → show `manage_url`) using Phase-4 opus reasoning over the specific client components — the same way content integration wires the content fetcher.
- Set the env var on Vercel (prod + preview), framework-prefixed.
- **Manage flow**: confirmation emails already link to `{manage_base_url}/manage/{token}` (centralized CMS page) — no client manage UI required.

## 4. Shared booking-module fixes (one pass)

**Fix A — de-hardcode "Stefan" (essential; emails go out for every client):**
- `booking_i18n.STRINGS['en']`: rewrite the host-name-bearing strings (confirm/reminder/cancel/reschedule subjects + subtext) to be **company-/booking-centric and host-name-neutral** (e.g. "Your booking is confirmed", "Reminder: your upcoming appointment"), interpolating `business_name` where a name is wanted — never a literal "Stefan".
- `booking_email.py` / `booking_manage_email.py` calendar-event titles: replace `Call with Stefan @ {business_name}` with a neutral `{service_name} @ {business_name}` (or `Booking @ {business_name}`).
- Keep `email_copy` per-tenant overrides working (the connector still sets them for service-specific wording).
- Regression: the existing booking email/preview tests updated to the neutral defaults; live tenants (roman-technologies, laurian) unaffected functionally.

**Fix B — iframe widget consumes per-tenant colors (for the optional fallback):**
- `BookingCalendar.tsx` (and its children): make the accent/primary visuals resolve from `--booking-accent`/`--booking-primary` (already set from tenant config) instead of the static global `--color-accent`. Fallback to the current global when the vars are unset (so Roman's own usage is unchanged).
- This is secondary (the primary path is custom client UI), but makes the turnkey iframe option theme-correct.

## 5. Smoke tests (Phase 5)

Against the freshly-provisioned slug (use a test customer + the e2e email short-circuit so no real mail sends):
1. `GET /booking/{slug}/services` → capture a `service_id`.
2. `GET /booking/{slug}/availability?service_id=…&from=…&to=…` → capture a `start_utc`.
3. `POST /booking/{slug}` (valid) → `success` + `booking_id` + `manage_url`; **honeypot** test (`website` non-empty → fake success, no row); **double-book** the same slot → **409**.
4. `GET /booking/manage/{token}` → `found`, can_reschedule/can_cancel.
5. `POST …/reschedule` `{slot_start}` → success (token rotates).
6. `POST …/cancel` → success.
7. `POST /projects/{slug}/bookings/email-preview` for `confirmation|reschedule|cancellation|reminder` → assert the rendered HTML carries the **company name + accent color** and **no "Stefan"**.
8. `POST /booking/cron/reminders` with `X-Cron-Secret` → `{sent}` (or skip if no due booking).
9. **Client build/render check**: the wired client repo compiles and the booking UI renders against the live API.

Any red test blocks Phase-6 "done" (consistent with the existing 5a–5g matrix discipline).

## 6. Self-improvement (widened)

- Add a **Booking** heading to `LEARNINGS.md` for booking-specific rules (detection, config mapping, provisioning order, wiring gotchas).
- **Widen the loop**: today it mainly records "should have caught" misses. Update `SKILL.md`'s self-improvement section so the agent records **both**: negative feedback ("don't do X / always do Y") **and** positive feedback ("Stefan praised Z — keep doing it"), each as a dated, one-line, append-only rule under the matching phase/area. These are global to the agent and fed into every future run, so corrections and confirmed-good behaviors both carry across all client projects.

## Out of scope

- Per-tenant From **address** / Resend domain (stays global) and per-tenant Google Calendar OAuth (clients use `calendar_provider='none'`).
- Real **non-English** booking UI/email translations (only host-name neutralization + `email_copy` overrides; a full `STRINGS` language is a separate effort).
- A bespoke per-client **manage page** (centralized page is the default; `lib/booking.ts` leaves the door open).
- Resource **capacity** > 1 / class bookings (module treats each resource as capacity 1).

## Testing strategy

- **Module fixes**: backend `test_booking_email*` / `email-preview` tests updated + green (neutral defaults); a widget test/snapshot for the color-var consumption.
- **Connector**: prompts tests (detection + booking manifest block emitted), scan/provision tests (mocked admin API: enable → settings PATCH with destination-email logic → services/resources/hours replace → `lib/booking.ts` generation), report-section rendering test.
- **Smoke**: the Phase-5 booking matrix above, runnable against a provisioned test tenant.

## File-level change summary

**Connector (`agents/CMS Connector - Website/`):** `prompts.py` (detection + `booking` manifest block + service-key/UI-wiring guidance), `scan.py` (`_provision` booking path: enable → settings/services/resources/hours, destination-email logic, `lib/booking.ts` generation + UI wiring, env), `output_writer.py` (booking config in `cms.config.json`/provision json), `phases/2-scan.md` (booking report section), `phases/4-integration.md` (booking provisioning + wiring steps), `phases/5-testing.md` (booking smoke matrix), `AGENTS.md` (glossary/contract: booking service + headless client contract), `LEARNINGS.md` + `SKILL.md` (booking rules + widened positive/negative feedback loop).

**Booking module (shared):** `backend/auth_service/services/booking_i18n.py` (neutral strings), `booking_email.py` + `booking_manage_email.py` (calendar titles), `frontend/src/components/booking/BookingCalendar.tsx` (+ children) (consume color vars). Tests updated accordingly.

**Generated per client (runtime output, not in this repo):** `lib/booking.ts`, booking config, wired booking UI, `BOOKING_API_BASE` env.
