# Custom Booking Widget — Design Spec

**Date:** 2026-06-03
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design); pending spec review
**Supersedes:** the Calendly embed in the home-page contact section
(`2026-06-03-home-contact-section-design.md`).

## Goal

Replace the Calendly iframe with a fully custom, on-brand booking widget that
Roman Technologies owns end-to-end: a 4-step flow (date → time → details →
confirmation) styled to match the contact form, with Motion transitions, no
iframe, and full responsiveness. Bookings are stored in Supabase, and **branded
emails are sent on booking** (to Stefan and the visitor) plus a **reminder ~1
hour before** the meeting. **No Google / calendar integration — no OAuth
prerequisite.**

## Why (the constraint that forced this)

Calendly renders in a cross-origin iframe, so its inputs, buttons, step
transitions, and scrollbar cannot be styled or controlled from our site. Owning
the UI is the only way to meet the requirements below.

## Requirements

- Custom 4-step booking UI: **date picker → time slots → details form →
  confirmation**, with smooth Motion transitions between steps.
- Visual parity with the contact form: same field styling, the **"Schedule"
  button identical to the contact form's "Send message" (`HeroButton`)**, and the
  confirmation reuses the gold spinner→checkmark (`SubmitFeedback`).
- The time-slot list **scrolls with the scrollbar visually hidden**.
- Times shown in the **visitor's local timezone** (auto-detected, label shown).
- Fully responsive (mobile / laptop / desktop); reduced-motion respected.
- Booking form fields: **Name (required), Email (required), Note (optional)**.
- On booking:
  - Store the booking in Supabase (prevents two people taking the same slot).
  - Send a **branded confirmation email to Stefan** (`stefanromanpers@gmail.com`)
    with the booking details — this is the core acceptance criterion.
  - Send a **branded confirmation email to the visitor** including a **standing
    meeting link** (set once in config).
- **~1-hour-before reminder:** a branded Resend email to the **visitor** whose
  header matches the issue-resolved email (`services/issue_resolved_email.py`),
  fired by **Supabase `pg_cron` + `pg_net`** (every 5 min) → a secured backend
  endpoint.
- Booking window: up to **120 days** ahead; minimum notice **2 hours**.
- Defaults: duration **45 min**, hours **Mon–Fri 09:00–18:00 Europe/Bucharest
  (EET)** — all configurable via backend settings.

## Explicit limitation (accepted trade-off)

Dropping Google means availability does **not** reflect Stefan's real calendar.
The widget only prevents double-booking **among bookings made through it**. If a
booked slot clashes with something on Stefan's personal calendar, he handles it
manually (he gets the booking email immediately with the visitor's address).

## Out of scope (v1 — YAGNI)

- Google Calendar / Meet integration, OAuth, real free/busy sync, auto-generated
  per-meeting links.
- Reschedule / cancel UI; multiple meeting types/durations; payments; manual
  timezone override; admin dashboard for bookings (the Supabase row + the email
  are the record for now).

## Architecture

### Frontend (`frontend/src/components/booking/`)

Replaces `CalendlyCalendar`. One orchestrator + four focused step components +
shared field styles.

- `BookingCalendar.tsx` — orchestrator. Holds wizard state
  (`step: "date" | "time" | "details" | "done"`, `selectedDate`, `selectedSlot`,
  submit `phase`), fetches availability/slots, performs the booking POST, and
  renders the active step inside an `AnimatePresence` with a directional
  slide+fade. Wrapped in `LazyMotion` + `MotionConfig reducedMotion="user"`.
- `MonthGrid.tsx` — month calendar (native `Date`, no date lib). Greys out past
  days, weekends/non-working days, and out-of-horizon days. A back/forward month
  pager. Selecting a day → advances to the time step. Days are buttons
  (cursor-pointer via the global rule).
- `TimeSlots.tsx` — vertical list of available slot times for the selected day,
  rendered in the visitor's timezone via `Intl.DateTimeFormat`. Scrolls with a
  **hidden scrollbar** (reuse the existing `.no-scrollbar` utility in
  `globals.css`). A "‹ back" control returns to the date step.
- `BookingDetailsForm.tsx` — Name / Email / Note(optional) using the **shared
  field styles** extracted from `ContactForm`, plus a honeypot field. Submit
  button is `HeroButton` ("Schedule"). Client-side validation mirrors
  `ContactForm` (name + valid email required; note free-form, optional).
- `BookingConfirmation.tsx` — reuses `SubmitFeedback` for the
  loading→success/error animation, then shows the booked date/time + a "check
  your email for the meeting link" line.
- Shared field styles — extract the `fieldBase` / `fieldOk` / `fieldErr` class
  strings currently inlined in `ContactForm.tsx` into one module
  (`components/ui/fieldStyles.ts`) imported by both the contact form and the
  booking form (no visual change to the contact form).

**Timezone:** the backend returns slot start times as **UTC ISO strings**; the
frontend formats them in the visitor's timezone with `Intl.DateTimeFormat`
(`Intl.DateTimeFormat().resolvedOptions().timeZone` for the label). No frontend
date dependency is added.

`ContactSection.tsx` swaps `<CalendlyCalendar />` for `<BookingCalendar />`.

### Backend (`backend/auth_service/`)

- `routers/booking.py` — new router (mounted at `/booking`):
  - `GET /booking/availability?from=YYYY-MM-DD&to=YYYY-MM-DD` → list of bookable
    **days** in range (working day, ≥ min-notice, ≤ horizon). Drives day
    enable/disable in `MonthGrid`.
  - `GET /booking/slots?date=YYYY-MM-DD&tz=<IANA>` → available 45-min slot start
    times (UTC ISO) for that day = working hours − existing confirmed bookings −
    min notice. `tz` is informational/logging only; computation is in Stefan's
    configured TZ, returned as UTC.
  - `POST /booking` → create a booking (see flow). Honeypot + IP rate-limit.
  - `POST /booking/cron/reminders` → secured by `X-Cron-Secret`; sends due
    reminders (see reminder flow).
- `services/booking_availability.py` — pure slot math (no I/O): given working
  hours, slot/buffer minutes, min-notice, horizon, a day, "now", and
  already-booked starts → returns available slot starts. Unit-tested in isolation.
- `services/booking_email.py` — branded **confirmation** emails, mirroring the
  `issue_resolved_email.py` structure (`render_*` + `send`, E2E guard, Resend via
  `urllib`, Cloudflare UA header, same zinc-900 header with `logo_dark.png`):
  - `send_host_notification(booking)` → to `BOOKING_HOST_EMAIL`, subject "New
    booking — {name}", detail box = name / email / date-time / note.
  - `send_visitor_confirmation(booking)` → to the visitor, subject "Your call
    with Stefan is booked", detail box = date-time + note, plus a "Join the call"
    button when `BOOKING_MEETING_URL` is set (else a line: "Stefan will email you
    the link.").
- `services/booking_reminder_email.py` — branded **reminder** to the visitor,
  same header, subtitle "Appointment reminder", detail box = meeting time
  (visitor's stored TZ) + the meeting link + note.

All three email modules reuse one shared header/footer helper so the issue-
resolved look is defined once.

### Database (Supabase)

`migrations/2026_06_03_bookings.sql` — table `public.bookings`:

| column | type | notes |
|---|---|---|
| `id` | uuid pk default `gen_random_uuid()` | |
| `start_utc` | timestamptz not null | slot start |
| `end_utc` | timestamptz not null | start + duration |
| `name` | text not null | |
| `email` | text not null | visitor |
| `note` | text | optional |
| `visitor_timezone` | text | IANA tz, for the reminder's time formatting |
| `status` | text not null default `'confirmed'` | `confirmed` \| `cancelled` |
| `reminder_sent_at` | timestamptz | dedup guard for the reminder |
| `created_at` | timestamptz default `now()` | |

- Partial unique index `unique (start_utc) where status = 'confirmed'` →
  race-safe double-book prevention.
- RLS **enabled, no public policies** → service-role (backend) only.
- Applied via Supabase MCP (per project convention).

`migrations/2026_06_03_booking_reminders_cron.sql`:
- `create extension if not exists pg_cron;` and `pg_net`.
- Reads the cron secret from **Supabase Vault** (`vault.decrypted_secrets`); the
  secret value is created out-of-band (`select vault.create_secret(...)`), **not
  committed**.
- Schedules `'send-booking-reminders'` every 5 min:
  `select net.http_post(url := '<backend>/booking/cron/reminders',
  headers := jsonb_build_object('Content-Type','application/json',
  'X-Cron-Secret', <secret>));`

### Config (`core/config.py` settings, all with defaults)

`BOOKING_TIMEZONE="Europe/Bucharest"`, `BOOKING_WORKING_DAYS="1,2,3,4,5"`,
`BOOKING_START_HOUR=9`, `BOOKING_END_HOUR=18`, `BOOKING_SLOT_MINUTES=45`,
`BOOKING_BUFFER_MINUTES=0`, `BOOKING_MIN_NOTICE_HOURS=2`,
`BOOKING_HORIZON_DAYS=120`, `BOOKING_HOST_EMAIL="stefanromanpers@gmail.com"`,
`BOOKING_MEETING_URL=""` (the standing Meet/Zoom link), `BOOKING_CRON_SECRET=""`.
**No `GOOGLE_*` vars and no new third-party Python dependencies.**

## Availability algorithm (`booking_availability.py`)

For a day `D` in `BOOKING_TIMEZONE`:
1. If `D` is not a working day, or `< today`, or `> now + horizon` → no slots.
2. Candidate starts: from `START_HOUR:00`, stepping `SLOT+BUFFER` minutes, while
   `start + SLOT ≤ END_HOUR:00` (45-min slots, buffer 0 → 09:00, 09:45, …,
   17:15). Localize to `BOOKING_TIMEZONE`, convert to UTC (DST-correct via
   `zoneinfo`).
3. Drop any start `< now + MIN_NOTICE_HOURS`.
4. Drop any start already taken by a confirmed booking.
5. Return remaining starts as UTC ISO.

## Booking flow (`POST /booking`)

Body: `{ slot_start (UTC ISO), name, email, note?, visitor_timezone?, website? }`.
1. Honeypot: non-empty `website` → silent `{success:true}`.
2. Validate: name non-empty, email matches regex, `slot_start` parses; `note`
   optional.
3. Recompute `end = start + SLOT`. Re-validate the slot is still legal (working
   hours, ≥ min notice, ≤ horizon) and free (Supabase) — defends a stale slot.
4. **Reserve**: insert `bookings` row (status `confirmed`); a unique-violation →
   `409` "That time was just taken" (race-safe via the partial unique index).
5. **Send emails best-effort** (booking row is the durable record; mirrors the
   issue-resolved convention that email failure must not undo the committed
   state): `send_host_notification` + `send_visitor_confirmation`, each wrapped
   in try/except + logged. (E2E guard respected.)
6. Return `{ success: true, start, end }`.
7. IP rate-limit (`limiter`, `key_func=client_ip`, e.g. `5/hour`).

## Reminder flow (`POST /booking/cron/reminders`)

1. Require header `X-Cron-Secret == BOOKING_CRON_SECRET` (else `403`).
2. Select `bookings` where `status='confirmed'` and `reminder_sent_at is null`
   and `start_utc > now()` and `start_utc <= now() + interval '65 minutes'`.
3. For each: `booking_reminder_email.send(...)` (E2E guard, failures logged),
   then set `reminder_sent_at = now()` (reminded at most once).
4. Return `{ sent: N }`. With the 5-min `pg_cron` + 65-min window, the reminder
   lands ~55–65 min before the meeting.

## Emails (all use the issue-resolved zinc-900 header)

- **On booking → Stefan** (`stefanromanpers@gmail.com`): "New booking — {name}",
  details box (name, email, date/time in `BOOKING_TIMEZONE`, note).
- **On booking → visitor**: "Your call with Stefan is booked", date/time (their
  TZ) + note + "Join the call" button (`BOOKING_MEETING_URL`) or the
  "Stefan will email you the link" fallback.
- **~1 h before → visitor**: "Reminder: your call with Stefan", subtitle
  "Appointment reminder", time + meeting link + note.
- All HTML-escaped (BE-006 pattern), with plain-text fallbacks.

## Abuse prevention

Honeypot field + IP rate-limit on `POST /booking`. Slot re-validation + the
partial unique index stop double-booking. The cron endpoint is secret-gated.
Email verification (double opt-in) is noted as future hardening, not v1.

## Error handling

- Slot taken between load and submit → `409`; the UI returns to the time step and
  refetches slots.
- Missing Resend config → host/visitor emails fail best-effort and are logged;
  the booking still commits and the UI shows success (the row is the record).
- Invalid body → `422`, surfaced as the UI error state with a mailto fallback.

## Testing

- **Backend unit (no network):** `booking_availability` slot math — working-day
  filter, min-notice cutoff, horizon, already-booked removal, buffer, DST
  correctness. The booking endpoint with Supabase + email `send` mocked: happy
  path (row inserted + both emails attempted), honeypot silent, 422 invalid, 409
  double-book. The reminder endpoint: 403 without secret, sends + stamps
  `reminder_sent_at`, idempotent on a second run. Email renderers: header/detail
  box renders with HTML-escaped fields; the visitor email includes the meeting
  button when `BOOKING_MEETING_URL` is set and the fallback line when it is empty.
- **Frontend:** typecheck + build. Optional Playwright: the 4 steps advance,
  slots render, validation blocks empty/invalid, the confirm animation plays
  (booking POST mocked / E2E-marked so nothing real is sent).
- Manual: book a slot locally (real `RESEND_API_KEY`) → confirm the email lands
  at `stefanromanpers@gmail.com` and the visitor email carries the standing link.

## Cleanup (Calendly removal)

Remove `CalendlyCalendar.tsx`, the `react-calendly` dependency, and the Calendly
entries in the `next.config.ts` CSP (`frame-src calendly.com`,
`script-src/style-src assets.calendly.com`).

## Conventions honored

`motion/react` (not framer-motion); surgical changes; reuse `HeroButton`,
`SubmitFeedback`, shared field styles, the issue-resolved email pattern, the
`limiter`, the E2E email guard, and the Supabase-MCP migration path. No
auto-commit. Buttons get cursor-pointer (global rule).
```
