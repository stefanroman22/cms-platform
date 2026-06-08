# Client Cancel / Reschedule — Design Spec

**Date:** 2026-06-04
**Author:** Stefan Roman (via Claude)
**Status:** Approved (design); pending spec review
**Extends:** the custom booking widget
(`2026-06-03-custom-booking-widget-design.md`).

## Goal

Let a client **cancel** (up to **24 hours** before) or **reschedule** (up to **12
hours** before) their booked call themselves, from a secure link in their
confirmation/reminder emails — no login. Cancelling removes the event from
Stefan's Google Calendar and emails both parties; rescheduling moves the same
booking to a new time and emails both parties. The owner (Stefan) does not
cancel/reschedule through this flow (out of scope for now).

## Requirements

- A single **"Manage your booking"** link in the client's emails opens a page
  showing the booking with **Cancel** and **Reschedule** actions.
- **Cancel:** allowed only while `now ≤ start − 24h`. Deletes the Google Calendar
  event, marks the booking `cancelled` (freeing the slot), and sends a
  cancellation email to **both** Stefan and the client.
- **Reschedule:** allowed only while `now ≤ start − 12h` **and the booking has
  been rescheduled fewer than 2 times**. The client picks a new slot (the
  existing booking calendar). The same booking is **moved in place** (row
  start/end updated, the Google event PATCHed to the new time, same standing Meet
  link), and a "moved" email goes to **both** parties (old → new time).
- After a window closes, or if already cancelled, the page explains why the
  action is unavailable and offers a direct-email fallback.
- Links are authorized by an unguessable per-booking token (no accounts).

## Out of scope (YAGNI)

- Owner-initiated cancel/reschedule.
- Editing name/email/note; partial refunds; waitlists.

## Data model (migration `backend/migrations/2026_06_04_bookings_manage.sql`)

Add to `public.bookings`:

| column | type | notes |
|---|---|---|
| `manage_token` | text | random `token_urlsafe(32)`; set on creation; the auth for management links. |
| `google_event_id` | text | the host-calendar event id, stored on creation (re-added) so the event can be deleted/moved. |
| `reschedule_count` | int not null default 0 | incremented on each reschedule; capped at `BOOKING_MAX_RESCHEDULES`. |

- Unique index on `manage_token`.
- `status` already supports `'cancelled'`; reschedule keeps `status='confirmed'`
  and just changes `start_utc`/`end_utc`.
- Applied via Supabase MCP.

## Config (`core/config.py`)

- `BOOKING_PUBLIC_BASE_URL: str = "https://roman-technologies.dev"` — base for the
  `/manage/{token}` link in emails (override locally to `http://localhost:3000`).
- `BOOKING_MAX_RESCHEDULES: int = 2` — a booking may be moved at most this many times.

## Backend

### Booking creation (modify `routers/booking.py::create_booking`)
- Generate `manage_token = secrets.token_urlsafe(32)`.
- Insert it on the row. After `google_calendar.create_event(...)` returns the
  event id, **update the row** with `google_event_id` (best-effort; logged on
  failure).
- Pass a `manage_url = f"{BOOKING_PUBLIC_BASE_URL}/manage/{manage_token}"` to the
  **client** confirmation email (and the reminder). The host email does not need
  it (Stefan doesn't self-manage).

### Endpoints (`routers/booking.py`)
- `GET /booking/manage/{token}` → `{ found, status, start_utc, end_utc,
  visitor_timezone, name, can_cancel, can_reschedule }`. `found=false` →
  still 200 with `found:false` (the page shows "link invalid"). `can_cancel` =
  `status=='confirmed' and now ≤ start − 24h`; `can_reschedule` =
  `status=='confirmed' and now ≤ start − 12h and reschedule_count <
  BOOKING_MAX_RESCHEDULES`. The response also carries `reschedule_count` and the
  remaining count for the page copy.
- `POST /booking/manage/{token}/cancel` →
  - 404 if no booking for the token; 409 if already cancelled; 403 if
    `now > start − 24h`.
  - Else: `google_calendar.delete_event(event_id)` (best-effort, logged), set
    `status='cancelled'`, send `booking_manage_email.send_cancellation` to host +
    client. Return `{ success: true }`.
- `POST /booking/manage/{token}/reschedule` (body `{ slot_start }`) →
  - 404 / 409 (cancelled) / 403 (`now > start − 12h`) as above.
  - **403 if `reschedule_count >= BOOKING_MAX_RESCHEDULES`** ("reschedule limit
    reached").
  - Validate the new `slot_start` is legal + free (reuse `_slot_is_free`).
  - **Move:** update the row `start_utc`/`end_utc` **and `reschedule_count =
    reschedule_count + 1`** (catch unique-violation → 409 "that time was just
    taken"); `google_calendar.update_event_time(event_id, new_start, new_end)`
    (best-effort, logged). Send `booking_manage_email.send_reschedule` to both
    (old → new). Return `{ success: true, start, end }`.
- All three are IP rate-limited (reuse `limiter`, `key_func=client_ip`).
  The token is the authorization.

### `services/google_calendar.py` additions
- `delete_event(event_id: str) -> None` → `DELETE /calendars/{cal}/events/{id}`
  (`sendUpdates=none`). 404/410 from Google (already gone) are swallowed.
- `update_event_time(event_id, start_utc, end_utc) -> None` →
  `PATCH /calendars/{cal}/events/{id}` body `{start:{dateTime}, end:{dateTime}}`
  (`sendUpdates=none`).
- Both no-op when `is_configured()` is false.

### `services/booking_manage_email.py` (new)
Branded (issue-resolved layout), Resend-over-urllib + E2E guard, HTML-escaped:
- `send_cancellation(*, booking, meeting_url)` → host ("{name} cancelled their
  call — {when}") + client ("Your call with Stefan is cancelled — {when}").
- `send_reschedule(*, booking, old_when, new_when, manage_url, meeting_url)` →
  host ("{name} moved their call: {old} → {new}") + client ("Your call is moved
  to {new}", with the Meet link + the manage link again).
  `booking` carries name/email + the labels.

## Frontend

### Route `app/(marketing)/manage/[token]/page.tsx` (client component)
- On mount, `GET /api/booking/manage/{token}`.
- States:
  - **not found** → "This link is invalid or expired."
  - **cancelled** → "This booking was cancelled."
  - **confirmed** → show the booking (date/time in `visitor_timezone` via
    `Intl`, in the same card styling), plus:
    - **Cancel call** button (shown when `can_cancel`) → a confirm step →
      `POST …/cancel` → success state ("Your call is cancelled").
    - **Reschedule** button (shown when `can_reschedule`) → renders
      `BookingCalendar` in reschedule mode.
    - When `!can_cancel`/`!can_reschedule`, show the reason: the time-window rule
      ("Cancellations close 24h before, rescheduling 12h before"), or — when
      `reschedule_count >= max` — "You've rescheduled this call the maximum of 2
      times." Always offer the email fallback (stefanromanpers@gmail.com).
- Reuses the gold `SubmitFeedback` for the cancel/reschedule async feedback.

### `BookingCalendar` reschedule mode
- New optional prop `reschedule?: { token: string; onDone: () => void }`.
- When set: header reads "Reschedule your call"; the flow is **date → time →
  confirm** (skip the details form — the client is known). Picking a slot goes to
  a small confirm step ("Move your call to {slot}?" → Confirm) which
  `POST`s to `/api/booking/manage/{token}/reschedule`, then shows the
  confirmation animation.
- Booking mode is unchanged.

## Data flow

```
Client email "Manage your booking" → /manage/{token}
  → GET /api/booking/manage/{token}  (booking + window flags)
  → Cancel:    POST …/cancel    → delete Google event, status=cancelled, emails both
  → Reschedule: pick slot → POST …/reschedule → move row + PATCH event, emails both
```

## Error handling

- Bad/old token → page shows "invalid link" (GET returns `found:false`).
- Action after its window → 403 → page shows the rule + email fallback.
- Reschedule slot taken between view and submit → 409 → return to the time step,
  refetch slots.
- Google delete/patch failure → logged, non-fatal (the DB row is the record;
  Stefan can remove a stray event manually). Email failure → logged, non-fatal.

## Testing

- **Backend unit (mocked Supabase + google + email):**
  - `manage` GET: returns flags; `can_cancel`/`can_reschedule` honor the 24h/12h
    windows and the `confirmed` status.
  - cancel: happy (status set + delete_event called + both emails), 403 too-late,
    404 bad token, 409 already-cancelled.
  - reschedule: happy (row moved, `reschedule_count` incremented,
    update_event_time called + both emails), 403 too-late, **403 when
    `reschedule_count >= max`**, 409 slot taken.
  - `google_calendar.delete_event` / `update_event_time`: correct method/path/body
    (mocked `_api`); 404/410 on delete swallowed.
  - `booking_manage_email` renderers: branded header, escaped fields, correct
    old/new labels.
  - `create_booking`: stores `manage_token`; updates row with `google_event_id`;
    client email contains the manage link.
- **Frontend:** typecheck + build. Optional Playwright: open a manage link
  (mocked GET), cancel flow + reschedule flow render and post.

## Conventions honored

`motion/react`; reuse `BookingCalendar`/`MonthGrid`/`TimeSlots`/`SubmitFeedback`,
the issue-resolved email layout, the `limiter`, the E2E guard, the urllib Google
client, and the Supabase-MCP migration path. Surgical changes; no auto-commit.
