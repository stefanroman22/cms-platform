# Bookings — Per-Tenant Branding, i18n, Notifications Idempotency & Reminder Offsets (Phase 4) Plan

> Design + plan combined (delegated build). Builds on P1–P3. **i18n: English only + mechanism** (adding a language later = one translation file). One additive DB migration (notifications log) applied via MCP; the `pg_cron` reminder job migration is written but **NOT applied** (the booking backend isn't deployed; a live cron would 404).

**Goal:** Emails + widget render per the tenant's brand (name/logo/colors/from-name) and locale (English now, pluggable); booking emails are idempotent (no double-sends on cron retries) via a `booking_notifications_log` table; the reminder cron honors each tenant's `reminder_offsets_min` instead of the legacy fixed ~1h window.

## Part 4a — Per-tenant email branding + i18n (backend)

**Critical constraint:** `email_layout.header/footer/shell` are shared with `issue_resolved_email.py`. All new params MUST be optional with defaults equal to today's Roman Technologies values, so the issue-resolved emails are byte-for-byte unchanged.

### `services/email_layout.py`
- Add an optional brand to `header`/`footer`/`shell`. Define a small frozen `Brand` dataclass (`business_name`, `logo_url`, `accent`, `canonical_url`) and default `DEFAULT_BRAND` = Roman Technologies (`business_name="Roman Technologies"`, `logo_url=f"{CANONICAL_URL}/logo_dark.png"`, `accent="#18181b"`, `canonical_url=CANONICAL_URL`).
- `header(subtitle, *, brand: Brand = DEFAULT_BRAND)` → use `brand.business_name`, `brand.logo_url`, and `brand.accent` for the header bg (fallback to the current zinc-900 if accent is None). `footer(*, brand=DEFAULT_BRAND)` → use `brand.canonical_url`/`business_name`. `shell` unchanged (or pass-through). Keep markup identical when `brand is DEFAULT_BRAND`.

### `services/booking_i18n.py` (new)
```python
"""Locale strings for booking emails + widget-facing copy. English now; add a
locale by adding a dict. `t(locale, key, **fmt)` falls back to 'en'."""
STRINGS = {
  "en": {
    "confirm_subject": "Your appointment is booked",
    "host_new_subject": "New booking — {name}",
    "reminder_subject": "Reminder: your appointment",
    "cancel_subject": "Your appointment is cancelled",
    "reschedule_subject": "Your appointment was moved",
    "confirmed_heading": "You're booked, {name}.",
    "reminder_heading": "Appointment reminder",
    "manage_cta": "Manage your booking",
    "join_cta": "Join the call",
    # ...the copy strings the email renderers need
  },
}
def t(locale: str | None, key: str, **fmt) -> str:
    table = STRINGS.get((locale or "en"), STRINGS["en"])
    return table.get(key, STRINGS["en"].get(key, key)).format(**fmt)
```

### `services/booking_email.py`, `booking_manage_email.py`, `booking_reminder_email.py`
- Each render/send function gains an optional `brand: email_layout.Brand | None = None` and `locale: str = "en"`; pass `brand` to `email_layout.header/footer` and use `booking_i18n.t(locale, ...)` for subjects + key copy (defaults reproduce current English). `_send` gains `from_name: str | None = None` → `from = f"{from_name or settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>"` (address stays the verified shared domain — per the brief, reuse the verified sender). Keep existing behavior when brand/locale/from_name are omitted.

### Wiring — `routers/booking.py` + `routers/booking_admin.py`
- Where emails are sent, build a `Brand` from the resolved `TenantConfig` (`business_name`, `logo_url`, `primary_color` as accent, canonical_url = `settings.manage_base_url`) and pass `brand=`, `locale=cfg.locale`, and `from_name=cfg.email_from_name or cfg.business_name` to the send functions.

### Tests
`test_booking_email.py` (+ manage/reminder): a render with a custom `Brand` shows the tenant business_name/accent and NOT "Roman Technologies"; default render still shows Roman Technologies (issue-resolved unaffected — add an assertion that `email_layout.header("x")` is unchanged). `from_name` override flows into the Resend `from`. `booking_i18n.t` fallback works.

## Part 4b — Notifications log idempotency + reminder offsets (backend)

### Migration — `backend/migrations/2026_06_05_booking_notifications_log.sql` (APPLY via MCP — additive)
```sql
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
create index if not exists booking_notif_booking on public.booking_notifications_log (booking_id);
alter table public.booking_notifications_log enable row level security;
```

### Migration — `backend/migrations/2026_06_05_booking_reminders_cron.sql` (WRITE, do NOT apply)
The `pg_cron` job (every 5 min → `net.http_post` to `<backend>/booking/cron/reminders` with the `X-Cron-Secret` from Vault). If a Phase-1 version already exists at that path, reuse/keep it; otherwise write it. Document at the top: "Apply at deploy time only — the cron target endpoint must be live first."

### `services/booking_repo.py` — idempotency helpers
```python
def notification_already_sent(idempotency_key: str) -> bool:
    sb = get_supabase_admin()
    res = sb.table("booking_notifications_log").select("id").eq("idempotency_key", idempotency_key).limit(1).execute()
    return bool(res.data)

def record_notification(*, tenant_id, booking_id, type, offset_min, idempotency_key,
                        status="sent", provider_id=None, error=None) -> None:
    sb = get_supabase_admin()
    sb.table("booking_notifications_log").insert({
        "tenant_id": tenant_id, "booking_id": booking_id, "type": type,
        "offset_min": offset_min, "idempotency_key": idempotency_key,
        "status": status, "provider_id": provider_id, "error": error,
        "sent_at": None if status != "sent" else "now()",
    }).execute()
```
(Use a Python ISO timestamp for sent_at rather than the literal "now()" string — set `datetime.now(UTC).isoformat()` when status=='sent'.)

### Reminder cron rewrite — `routers/booking.py::send_reminders`
- Replace the fixed 65-min window + `reminder_sent_at` stamp with **per-offset, notifications-log-deduped** sending:
  - Scan confirmed upcoming bookings within `now .. now + max(all tenants' max offset)`; for efficiency keep scanning `confirmed`, `reminder` is per (booking, offset).
  - For each booking: load its tenant cfg; for each `offset_min` in `cfg.reminder_offsets_min` (skip if `not cfg.reminders_enabled`): if `now` is within a 5-min send window of `start - offset_min` (i.e. `start - offset_min - 5min <= now < start - offset_min`) AND `not booking_repo.notification_already_sent(key)` where `key = f"{booking_id}:reminder:{offset_min}"`: send the reminder (with brand+locale), then `record_notification(...)`.
  - Return `{sent: N}`.
- The confirmation/cancel/reschedule sends in create/cancel/reschedule should also `record_notification` (type confirm_customer/confirm_owner/cancel/reschedule, offset_min=None, key = f"{booking_id}:{type}") and skip if already sent — so retries don't double-send. Best-effort: a logging-only failure still must not break the booking.

### Tests
`test_booking_router.py` reminder tests: with `reminder_offsets_min=[1440,120]`, a booking 2h out → the 120-offset reminder fires once and is skipped on a second cron run (mock `notification_already_sent` → False then True); offsets not yet due don't fire; `reminders_enabled=False` → nothing. Repo tests for the two helpers (mock supabase).

## Part 4c — Widget i18n mechanism (frontend)

### `frontend/src/components/booking/i18n.ts` (new)
```typescript
export const STRINGS = {
  en: {
    bookHeading: "Book an appointment",
    pickService: "Choose a service",
    pickDate: "Pick a date",
    pickTime: "Pick a time",
    yourDetails: "Your details",
    name: "Name", email: "Email", note: "Note (optional)",
    schedule: "Schedule", booked: "You're booked",
    checkEmail: "Check your email for confirmation.",
    // ...every visible string in the widget
  },
} as const;
export type Locale = keyof typeof STRINGS;
export function tw(locale: string, key: keyof typeof STRINGS["en"]): string {
  return (STRINGS[(locale as Locale)] ?? STRINGS.en)[key] ?? STRINGS.en[key];
}
```
- Refactor `BookingCalendar` (+ MonthGrid/TimeSlots/BookingDetailsForm/BookingConfirmation) to pull visible copy from `tw(locale, key)` where `locale` comes from the fetched `/config` (`config.locale`, default "en"). English output must be unchanged from today. This is the mechanism; only `en` is populated.

### Tests / verify
`npx tsc --noEmit` clean; `npm test -- --run` green. (No new behavior to unit-test beyond types; a tiny test that `tw("xx","schedule")` falls back to English is nice-to-have.)

## Verify (whole phase)
- Apply the notifications-log migration via Supabase MCP (additive). Do NOT apply the pg_cron migration.
- Backend: `pytest auth_service/tests/ -q` green (report counts).
- Frontend: `npx tsc --noEmit` + `npm test -- --run` green; milestone `npm run build`.
- No commit.

## Notes
- `from` email address stays the shared verified Resend domain (`noreply@roman-technologies.dev`); only the display name is per-tenant (verifying per-tenant sender domains is out of scope).
- `frame-ancestors`/embedding unchanged from P3.
- After P4, the whole brief is implemented (minus the explicitly-deferred deploy steps: committing the code, deploying the backend, applying the pg_cron migration, and verifying per-tenant Resend domains).
