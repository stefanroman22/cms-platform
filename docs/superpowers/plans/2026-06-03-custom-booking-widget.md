# Custom Booking Widget Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the Calendly iframe with a fully custom, on-brand 4-step booking widget backed by Supabase, with branded confirmation emails (to Stefan + visitor) on booking and a branded reminder ~1h before — no Google/OAuth.

**Architecture:** FastAPI `booking` router (availability/slots/book/reminders) + pure slot-math service + three Resend email modules sharing the issue-resolved header; Supabase `bookings` table (race-safe via a partial unique index) and a `pg_cron`+`pg_net` reminder trigger. Frontend: a `BookingCalendar` wizard (date→time→details→confirm) with `motion/react` transitions, reusing `HeroButton`, `SubmitFeedback`, and field styles shared with `ContactForm`.

**Tech Stack:** Next.js 16 + TypeScript + Tailwind v4 + `motion/react`; FastAPI + Python 3.13 (`zoneinfo`, no new deps) + Supabase + Resend + pg_cron/pg_net.

**Conventions:**
- `motion/react`, never `framer-motion`.
- **No auto-commit per task** (project rule). Implement all tasks; one commit at the end when Stefan says so. Per-task work is still split into bite-sized steps.
- No `npm run build` after every change; build once at the verification milestone.
- Backend tests: from `backend/`, `source venv/Scripts/activate && python -m pytest <path> -v`.
- Migrations applied via the Supabase MCP `apply_migration` tool (don't ask Stefan), then the `.sql` is also saved under `backend/migrations/`.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/migrations/2026_06_03_bookings.sql` | Create + apply (MCP) | `bookings` table + partial unique index + RLS. |
| `backend/migrations/2026_06_03_booking_reminders_cron.sql` | Create + apply (MCP) | pg_cron + pg_net reminder job (Vault secret). |
| `backend/auth_service/core/config.py` | Modify | Booking settings. |
| `backend/auth_service/services/booking_availability.py` | Create | Pure slot math. |
| `backend/auth_service/services/email_layout.py` | Create | Shared zinc-900 header/footer HTML (DRY). |
| `backend/auth_service/services/booking_email.py` | Create | Host + visitor confirmation emails. |
| `backend/auth_service/services/booking_reminder_email.py` | Create | ~1h-before reminder email. |
| `backend/auth_service/routers/booking.py` | Create | `/booking/*` endpoints. |
| `backend/auth_service/main.py` | Modify | Mount the booking router. |
| `backend/auth_service/tests/test_booking_*.py` | Create | Unit tests. |
| `frontend/src/components/ui/fieldStyles.ts` | Create | Shared input class strings. |
| `frontend/src/components/contact/ContactForm.tsx` | Modify | Import shared field styles. |
| `frontend/src/lib/bookingDates.ts` | Create | Native date helpers (month grid, keys). |
| `frontend/src/components/booking/MonthGrid.tsx` | Create | Month calendar step. |
| `frontend/src/components/booking/TimeSlots.tsx` | Create | Slot list step. |
| `frontend/src/components/booking/BookingDetailsForm.tsx` | Create | Details step. |
| `frontend/src/components/booking/BookingConfirmation.tsx` | Create | Confirm step. |
| `frontend/src/components/booking/BookingCalendar.tsx` | Create | Wizard orchestrator. |
| `frontend/src/components/contact/ContactSection.tsx` | Modify | Use `BookingCalendar`. |
| `frontend/src/components/contact/CalendlyCalendar.tsx` | Delete | Calendly removed. |
| `frontend/package.json` | Modify | Drop `react-calendly`. |
| `frontend/next.config.ts` | Modify | Drop Calendly CSP entries. |

---

## Task 1: `bookings` table migration

**Files:** Create `backend/migrations/2026_06_03_bookings.sql`

- [ ] **Step 1: Write the migration SQL**

```sql
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
```

- [ ] **Step 2: Apply via Supabase MCP**

Use the `apply_migration` MCP tool with name `2026_06_03_bookings` and the SQL above. Then confirm with `list_tables` that `public.bookings` exists with the listed columns.

- [ ] **Step 3: Verify the unique index**

Use the MCP `execute_sql`:
```sql
select indexname from pg_indexes where tablename = 'bookings';
```
Expected: includes `bookings_confirmed_start_uniq` and `bookings_reminder_scan`.

---

## Task 2: Booking config settings

**Files:** Modify `backend/auth_service/core/config.py`

- [ ] **Step 1: Add settings fields**

In `class Settings`, after the `RESEND_*` block (around line 31), add:

```python
    # Booking widget
    BOOKING_TIMEZONE: str = "Europe/Bucharest"
    BOOKING_WORKING_DAYS: str = "1,2,3,4,5"  # ISO weekdays, Mon=1
    BOOKING_START_HOUR: int = 9
    BOOKING_END_HOUR: int = 18
    BOOKING_SLOT_MINUTES: int = 45
    BOOKING_BUFFER_MINUTES: int = 0
    BOOKING_MIN_NOTICE_HOURS: int = 2
    BOOKING_HORIZON_DAYS: int = 120
    BOOKING_HOST_EMAIL: str = "stefanromanpers@gmail.com"
    BOOKING_MEETING_URL: str = ""  # standing Meet/Zoom link, shown in emails
    BOOKING_CRON_SECRET: str = ""  # guards POST /booking/cron/reminders

    @property
    def booking_working_days(self) -> set[int]:
        return {int(d) for d in self.BOOKING_WORKING_DAYS.split(",") if d.strip()}
```

- [ ] **Step 2: Verify import still works**

Run: `source venv/Scripts/activate && python -c "from auth_service.core.config import settings; print(settings.booking_working_days)"`
Expected: `{1, 2, 3, 4, 5}`.

---

## Task 3: Slot-math service (TDD)

**Files:** Create `backend/auth_service/services/booking_availability.py`, Test `backend/auth_service/tests/test_booking_availability.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_availability.py
from datetime import datetime, date
from zoneinfo import ZoneInfo

from auth_service.services.booking_availability import available_slot_starts

UTC = ZoneInfo("UTC")
COMMON = dict(
    tz_name="Europe/Bucharest",
    working_days={1, 2, 3, 4, 5},
    start_hour=9,
    end_hour=18,
    slot_minutes=45,
    buffer_minutes=0,
    min_notice_hours=2,
    horizon_days=120,
    booked_starts_utc=set(),
)


def test_weekday_returns_twelve_slots():
    # A Wednesday far in the future, now well before it.
    slots = available_slot_starts(
        day=date(2026, 6, 10),  # Wednesday
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        **COMMON,
    )
    assert len(slots) == 12
    # First slot is 09:00 Europe/Bucharest = 06:00 UTC (EEST, +3 in June).
    assert slots[0] == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)


def test_weekend_returns_nothing():
    slots = available_slot_starts(
        day=date(2026, 6, 13),  # Saturday
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        **COMMON,
    )
    assert slots == []


def test_past_day_returns_nothing():
    slots = available_slot_starts(
        day=date(2026, 6, 1),
        now_utc=datetime(2026, 6, 2, 6, 0, tzinfo=UTC),
        **COMMON,
    )
    assert slots == []


def test_beyond_horizon_returns_nothing():
    slots = available_slot_starts(
        day=date(2026, 12, 1),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        **COMMON,
    )
    assert slots == []


def test_min_notice_drops_near_slots():
    # "Now" is 2026-06-10 05:30 UTC (08:30 Bucharest). With 2h notice, slots
    # before 07:30 UTC (10:30 Bucharest) are dropped: 09:00 and 09:45 go.
    slots = available_slot_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 10, 5, 30, tzinfo=UTC),
        **COMMON,
    )
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) not in slots  # 09:00 local
    assert datetime(2026, 6, 10, 7, 30, tzinfo=UTC) in slots     # 10:30 local


def test_booked_start_excluded():
    booked = {datetime(2026, 6, 10, 6, 0, tzinfo=UTC)}  # 09:00 local taken
    slots = available_slot_starts(
        day=date(2026, 6, 10),
        now_utc=datetime(2026, 6, 1, 6, 0, tzinfo=UTC),
        **{**COMMON, "booked_starts_utc": booked},
    )
    assert datetime(2026, 6, 10, 6, 0, tzinfo=UTC) not in slots
    assert len(slots) == 11
```

- [ ] **Step 2: Run it — expect failure**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_availability.py -v`
Expected: ImportError / module not found.

- [ ] **Step 3: Implement the service**

```python
# backend/auth_service/services/booking_availability.py
"""Pure availability math for the booking widget — no I/O, fully unit-tested.

Slots live in the host timezone's working hours; the caller supplies the set of
already-taken starts (in UTC) and "now" (UTC). Returns UTC, tz-aware datetimes.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

_UTC = ZoneInfo("UTC")


def available_slot_starts(
    *,
    day: date,
    now_utc: datetime,
    tz_name: str,
    working_days: set[int],
    start_hour: int,
    end_hour: int,
    slot_minutes: int,
    buffer_minutes: int,
    min_notice_hours: int,
    horizon_days: int,
    booked_starts_utc: set[datetime],
) -> list[datetime]:
    tz = ZoneInfo(tz_name)
    today_host = now_utc.astimezone(tz).date()

    if day.isoweekday() not in working_days:
        return []
    if day < today_host or day > today_host + timedelta(days=horizon_days):
        return []

    earliest = now_utc + timedelta(hours=min_notice_hours)
    step = slot_minutes + buffer_minutes

    cursor = datetime.combine(day, time(hour=start_hour), tzinfo=tz)
    end_boundary = datetime.combine(day, time(hour=end_hour), tzinfo=tz)

    slots: list[datetime] = []
    while cursor + timedelta(minutes=slot_minutes) <= end_boundary:
        start_utc = cursor.astimezone(_UTC)
        if start_utc >= earliest and start_utc not in booked_starts_utc:
            slots.append(start_utc)
        cursor += timedelta(minutes=step)
    return slots
```

- [ ] **Step 4: Run it — expect pass**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_availability.py -v`
Expected: 6 passed.

---

## Task 4: Shared email layout + confirmation emails (TDD)

**Files:** Create `backend/auth_service/services/email_layout.py`, `backend/auth_service/services/booking_email.py`, Test `backend/auth_service/tests/test_booking_email.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_email.py
from auth_service.services.booking_email import (
    render_host_html,
    render_visitor_html,
)

BOOKING = {
    "name": "Jane <b>Doe</b>",
    "email": "jane@acme.com",
    "note": "Discuss a new site",
    "when_label": "Wed, 10 Jun 2026 · 09:00 (Europe/Bucharest)",
}


def test_host_email_has_header_and_escaped_name():
    html = render_host_html(booking=BOOKING)
    assert "Roman Technologies" in html
    assert "logo_dark.png" in html
    assert "Jane &lt;b&gt;Doe&lt;/b&gt;" in html  # escaped
    assert "jane@acme.com" in html


def test_visitor_email_includes_meeting_button_when_url_set():
    html = render_visitor_html(booking=BOOKING, meeting_url="https://meet.example/abc")
    assert "https://meet.example/abc" in html
    assert "Join the call" in html


def test_visitor_email_fallback_when_no_url():
    html = render_visitor_html(booking=BOOKING, meeting_url="")
    assert "Join the call" not in html
    assert "email you the link" in html
```

- [ ] **Step 2: Run it — expect failure**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_email.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement the shared layout**

```python
# backend/auth_service/services/email_layout.py
"""Shared branded email chrome — the zinc-900 header + footer used by the
issue-resolved, booking confirmation, and reminder emails. Inline styles only
(mail clients strip <style>)."""

from __future__ import annotations

CANONICAL_URL = "https://roman-technologies.dev"


def header(subtitle: str) -> str:
    return f"""<tr><td style="background:#18181b;padding:24px 32px">
  <table cellpadding="0" cellspacing="0"><tr>
    <td width="44" height="44" valign="middle" style="background:#18181b;border-radius:10px">
      <img src="{CANONICAL_URL}/logo_dark.png" width="44" height="44" alt="" style="display:block;border:0;border-radius:10px">
    </td>
    <td style="vertical-align:middle;padding-left:14px">
      <p style="margin:0;color:#fff;font-size:18px;font-weight:600;letter-spacing:-0.01em">Roman Technologies</p>
      <p style="margin:2px 0 0;color:#a1a1aa;font-size:12px">{subtitle}</p>
    </td>
  </tr></table>
</td></tr>"""


def footer() -> str:
    return f"""<tr><td style="padding:32px 32px 28px;border-top:1px solid #f4f4f5">
  <p style="margin:0;font-size:12px;color:#a1a1aa;line-height:1.5">
    Sent from <a href="{CANONICAL_URL}" style="color:#71717a;text-decoration:none">roman-technologies.dev</a> &middot;
    &copy; 2026 Roman Technologies
  </p>
</td></tr>"""


def shell(inner: str) -> str:
    return f"""<!DOCTYPE html><html lang="en"><head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f5f5f4;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Helvetica,Arial,sans-serif;color:#27272a">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f5f5f4;padding:40px 20px"><tr><td align="center">
    <table width="600" cellpadding="0" cellspacing="0" style="max-width:600px;width:100%;background:#fff;border:1px solid #e4e4e7;border-radius:12px;overflow:hidden">
      {inner}
    </table>
  </td></tr></table>
</body></html>"""
```

- [ ] **Step 4: Implement the confirmation emails**

```python
# backend/auth_service/services/booking_email.py
"""Branded booking-confirmation emails: one to the host (Stefan), one to the
visitor. Mirrors issue_resolved_email's Resend-over-urllib send + E2E guard."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings
from . import email_layout


def _detail_box(rows: list[tuple[str, str]]) -> str:
    body = "".join(
        f'<p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;'
        f'text-transform:uppercase;color:#71717a">{label}</p>'
        f'<p style="margin:0 0 14px;font-size:15px;color:#18181b">{value}</p>'
        for label, value in rows
    )
    return (
        '<tr><td style="padding:8px 32px"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">'
        f'<tr><td style="padding:18px 22px">{body}</td></tr></table></td></tr>'
    )


def render_host_html(*, booking: dict) -> str:
    name = html.escape(booking["name"])
    email = html.escape(booking["email"])
    when = html.escape(booking["when_label"])
    note = html.escape(booking.get("note") or "—").replace("\n", "<br>")
    inner = (
        email_layout.header("New booking")
        + '<tr><td style="padding:32px 32px 8px"><h1 style="margin:0;font-size:22px;font-weight:600;color:#18181b">New call booked</h1></td></tr>'
        + _detail_box([("When", when), ("Name", name), ("Email", email), ("Note", note)])
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def render_visitor_html(*, booking: dict, meeting_url: str) -> str:
    name = html.escape(booking["name"])
    when = html.escape(booking["when_label"])
    note = html.escape(booking.get("note") or "—").replace("\n", "<br>")
    if meeting_url:
        cta = (
            '<tr><td style="padding:24px 32px 8px" align="center">'
            f'<a href="{html.escape(meeting_url)}" style="display:inline-block;background:#18181b;'
            'color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">'
            'Join the call &rarr;</a></td></tr>'
        )
    else:
        cta = (
            '<tr><td style="padding:16px 32px 8px" align="center">'
            '<p style="margin:0;font-size:13px;color:#71717a">Stefan will email you the link before the call.</p>'
            '</td></tr>'
        )
    inner = (
        email_layout.header("Appointment confirmed")
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">You’re booked, {name}.</h1>'
        + '<p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">Your call with Stefan is confirmed.</p></td></tr>'
        + _detail_box([("When", when), ("Note", note)])
        + cta
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def _send(*, to_email: str, subject: str, html_body: str, text_body: str) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, subject):
        return short_circuit_response(f"booking:{to_email}")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": subject,
        "html": html_body,
        "text": text_body,
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e


def send_host_notification(*, booking: dict) -> dict:
    text = f"New call booked\n\nWhen: {booking['when_label']}\nName: {booking['name']}\nEmail: {booking['email']}\nNote: {booking.get('note') or '-'}\n"
    return _send(
        to_email=settings.BOOKING_HOST_EMAIL,
        subject=f"New booking — {booking['name']}",
        html_body=render_host_html(booking=booking),
        text_body=text,
    )


def send_visitor_confirmation(*, booking: dict) -> dict:
    url = settings.BOOKING_MEETING_URL
    link_line = f"Join the call: {url}\n" if url else "Stefan will email you the link before the call.\n"
    text = f"You're booked, {booking['name']}.\n\nWhen: {booking['when_label']}\nNote: {booking.get('note') or '-'}\n{link_line}"
    return _send(
        to_email=booking["email"],
        subject="Your call with Stefan is booked",
        html_body=render_visitor_html(booking=booking, meeting_url=url),
        text_body=text,
    )
```

- [ ] **Step 5: Run it — expect pass**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_email.py -v`
Expected: 3 passed.

---

## Task 5: Reminder email (TDD)

**Files:** Create `backend/auth_service/services/booking_reminder_email.py`, Test `backend/auth_service/tests/test_booking_reminder_email.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_reminder_email.py
from auth_service.services.booking_reminder_email import render_html


def test_reminder_html_has_header_time_and_note():
    html_body = render_html(
        name="Jane",
        when_label="Today · 15:00 (Europe/London)",
        note="bring the brief",
        meeting_url="https://meet.example/abc",
    )
    assert "Roman Technologies" in html_body
    assert "Appointment reminder" in html_body
    assert "15:00 (Europe/London)" in html_body
    assert "https://meet.example/abc" in html_body


def test_reminder_html_escapes_fields():
    html_body = render_html(
        name="<x>", when_label="t", note="<script>", meeting_url=""
    )
    assert "&lt;x&gt;" in html_body
    assert "&lt;script&gt;" in html_body
```

- [ ] **Step 2: Run it — expect failure**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_reminder_email.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement**

```python
# backend/auth_service/services/booking_reminder_email.py
"""~1h-before reminder email to the visitor. Same branded chrome; Resend-over-
urllib send with E2E guard (mirrors booking_email)."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings
from . import email_layout


def render_html(*, name: str, when_label: str, note: str | None, meeting_url: str) -> str:
    safe_name = html.escape(name)
    safe_when = html.escape(when_label)
    safe_note = html.escape(note or "—").replace("\n", "<br>")
    if meeting_url:
        cta = (
            '<tr><td style="padding:24px 32px 8px" align="center">'
            f'<a href="{html.escape(meeting_url)}" style="display:inline-block;background:#18181b;'
            'color:#fff;text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">'
            'Join the call &rarr;</a></td></tr>'
        )
    else:
        cta = ""
    box = (
        '<tr><td style="padding:8px 32px"><table width="100%" cellpadding="0" cellspacing="0" '
        'style="margin-top:16px;background:#fafafa;border:1px solid #e4e4e7;border-radius:8px">'
        '<tr><td style="padding:18px 22px">'
        '<p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">When</p>'
        f'<p style="margin:0 0 14px;font-size:15px;color:#18181b">{safe_when}</p>'
        '<p style="margin:0 0 4px;font-size:11px;font-weight:600;letter-spacing:0.08em;text-transform:uppercase;color:#71717a">Note</p>'
        f'<p style="margin:0;font-size:15px;color:#18181b">{safe_note}</p>'
        '</td></tr></table></td></tr>'
    )
    inner = (
        email_layout.header("Appointment reminder")
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">Your call is in about an hour, {safe_name}.</h1></td></tr>'
        + box
        + cta
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def render_text(*, name: str, when_label: str, note: str | None, meeting_url: str) -> str:
    link = f"Join: {meeting_url}\n" if meeting_url else ""
    return f"Reminder — your call with Stefan is in about an hour.\n\nWhen: {when_label}\nNote: {note or '-'}\n{link}"


def send(*, to_email: str, name: str, when_label: str, note: str | None, meeting_url: str) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, name, when_label):
        return short_circuit_response(f"booking_reminder:{to_email}")
    if not settings.RESEND_API_KEY:
        raise RuntimeError("RESEND_API_KEY not configured on this backend")

    body = {
        "from": f"{settings.RESEND_FROM_NAME} <{settings.RESEND_FROM_EMAIL}>",
        "to": to_email,
        "subject": "Reminder: your call with Stefan",
        "html": render_html(name=name, when_label=when_label, note=note, meeting_url=meeting_url),
        "text": render_text(name=name, when_label=when_label, note=note, meeting_url=meeting_url),
    }
    req = urllib.request.Request(
        "https://api.resend.com/emails",
        data=json.dumps(body).encode(),
        headers={
            "Authorization": f"Bearer {settings.RESEND_API_KEY}",
            "Content-Type": "application/json",
            "User-Agent": "roman-technologies-cms-backend/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Resend {e.code}: {e.read().decode()}") from e
```

- [ ] **Step 4: Run it — expect pass**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_reminder_email.py -v`
Expected: 2 passed.

---

## Task 6: Booking router (TDD) + mount

**Files:** Create `backend/auth_service/routers/booking.py`, Test `backend/auth_service/tests/test_booking_router.py`, Modify `backend/auth_service/main.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/auth_service/tests/test_booking_router.py
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _sb_chain(execute_data):
    sb = MagicMock()
    for m in ["table", "select", "insert", "eq", "gte", "lte", "delete", "update", "is_"]:
        getattr(sb, m).return_value = sb
    sb.execute.return_value = type("R", (), {"data": execute_data})()
    return sb


def test_slots_returns_iso_starts(client):
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb_chain([])):
        r = client.get("/booking/slots?date=2026-06-10&tz=Europe/London")
    assert r.status_code == 200, r.text
    slots = r.json()["slots"]
    assert isinstance(slots, list) and len(slots) == 12
    assert slots[0].endswith("Z") or "+00:00" in slots[0]


def test_booking_honeypot_silently_accepted(client):
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb_chain([])):
        r = client.post("/booking", json={
            "slot_start": "2026-06-10T06:00:00+00:00",
            "name": "Bot", "email": "b@b.com", "website": "x",
        })
    assert r.status_code == 200
    assert r.json()["success"] is True


def test_booking_422_on_bad_email(client):
    r = client.post("/booking", json={
        "slot_start": "2026-06-10T06:00:00+00:00", "name": "J", "email": "nope",
    })
    assert r.status_code == 422


def test_booking_happy_path_inserts_and_emails(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    sb = _sb_chain([{"id": "b1"}])
    with (
        patch("auth_service.routers.booking.get_supabase_admin", return_value=sb),
        patch("auth_service.routers.booking.booking_email.send_host_notification") as host,
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation") as vis,
        patch("auth_service.routers.booking._slot_is_free", return_value=True),
    ):
        r = client.post("/booking", json={
            "slot_start": "2099-06-10T06:00:00+00:00",
            "name": "Jane", "email": "jane@acme.com", "note": "hi",
            "visitor_timezone": "Europe/London",
        })
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
    host.assert_called_once()
    vis.assert_called_once()


def test_reminders_requires_secret(client, monkeypatch):
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    r = client.post("/booking/cron/reminders")
    assert r.status_code == 403


def test_reminders_sends_and_marks(client, monkeypatch):
    monkeypatch.setattr(settings, "BOOKING_CRON_SECRET", "s3cr3t")
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    due = [{"id": "b1", "email": "j@a.com", "name": "Jane", "note": None,
            "start_utc": "2099-06-10T06:00:00+00:00", "visitor_timezone": "Europe/London"}]
    sb = _sb_chain(due)
    with (
        patch("auth_service.routers.booking.get_supabase_admin", return_value=sb),
        patch("auth_service.routers.booking.booking_reminder_email.send") as snd,
    ):
        r = client.post("/booking/cron/reminders", headers={"X-Cron-Secret": "s3cr3t"})
    assert r.status_code == 200
    assert r.json()["sent"] == 1
    snd.assert_called_once()
```

- [ ] **Step 2: Run it — expect failure**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_router.py -v`
Expected: ImportError / 404s.

- [ ] **Step 3: Implement the router**

```python
# backend/auth_service/routers/booking.py
"""Custom booking widget API. Same-origin (reached via the frontend /api proxy),
so abuse protection is rate-limit + honeypot, not origin allow-listing."""

from __future__ import annotations

import re
from datetime import UTC, date, datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import APIRouter, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from ..core.config import settings
from ..core.limiter import client_ip, limiter
from ..services import booking_email, booking_reminder_email
from ..services.booking_availability import available_slot_starts
from ..services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/booking", tags=["booking"])

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_UTC = ZoneInfo("UTC")


def _slot_kwargs() -> dict:
    return dict(
        tz_name=settings.BOOKING_TIMEZONE,
        working_days=settings.booking_working_days,
        start_hour=settings.BOOKING_START_HOUR,
        end_hour=settings.BOOKING_END_HOUR,
        slot_minutes=settings.BOOKING_SLOT_MINUTES,
        buffer_minutes=settings.BOOKING_BUFFER_MINUTES,
        min_notice_hours=settings.BOOKING_MIN_NOTICE_HOURS,
        horizon_days=settings.BOOKING_HORIZON_DAYS,
    )


def _booked_starts(day: date) -> set[datetime]:
    """Confirmed booking starts on the given host-tz day (returned as UTC)."""
    tz = ZoneInfo(settings.BOOKING_TIMEZONE)
    day_start = datetime.combine(day, datetime.min.time(), tzinfo=tz).astimezone(_UTC)
    day_end = day_start + timedelta(days=1)
    sb = get_supabase_admin()
    rows = (
        sb.table("bookings")
        .select("start_utc")
        .eq("status", "confirmed")
        .gte("start_utc", day_start.isoformat())
        .lte("start_utc", day_end.isoformat())
        .execute()
    )
    out: set[datetime] = set()
    for r in rows.data or []:
        out.add(datetime.fromisoformat(r["start_utc"]).astimezone(_UTC))
    return out


def _slot_is_free(start_utc: datetime) -> bool:
    day_host = start_utc.astimezone(ZoneInfo(settings.BOOKING_TIMEZONE)).date()
    legal = available_slot_starts(
        day=day_host, now_utc=datetime.now(UTC),
        booked_starts_utc=_booked_starts(day_host), **_slot_kwargs(),
    )
    return start_utc in legal


def _when_label(start_utc: datetime, tz_name: str) -> str:
    tz = ZoneInfo(tz_name) if tz_name else ZoneInfo(settings.BOOKING_TIMEZONE)
    local = start_utc.astimezone(tz)
    return local.strftime("%a, %d %b %Y · %H:%M ") + f"({tz_name or settings.BOOKING_TIMEZONE})"


@router.get("/availability")
def availability(from_: str = "", to: str = "") -> JSONResponse:
    # Query params are `from` and `to`; FastAPI maps `from_` via alias below.
    raise HTTPException(status_code=500, detail="unreachable")  # replaced in Step 3b


@router.get("/slots")
def slots(date: str, tz: str = "") -> JSONResponse:
    try:
        day = datetime.strptime(date, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad date") from exc
    starts = available_slot_starts(
        day=day, now_utc=datetime.now(UTC),
        booked_starts_utc=_booked_starts(day), **_slot_kwargs(),
    )
    return JSONResponse(content={"slots": [s.isoformat() for s in starts]})


class BookingRequest(BaseModel):
    slot_start: str
    name: str
    email: str
    note: str = ""
    visitor_timezone: str = ""
    website: str = ""  # honeypot


@router.post("")
@limiter.limit("5/hour", key_func=client_ip)
async def create_booking(request: Request, body: BookingRequest) -> JSONResponse:
    if body.website.strip():
        return JSONResponse(content={"success": True})

    name = body.name.strip()
    email = body.email.strip()
    note = body.note.strip()
    if not name or not _EMAIL_RE.match(email):
        raise HTTPException(status_code=422, detail="Invalid booking")
    try:
        start = datetime.fromisoformat(body.slot_start).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad slot_start") from exc

    if not _slot_is_free(start):
        raise HTTPException(status_code=409, detail="That time was just taken")

    end = start + timedelta(minutes=settings.BOOKING_SLOT_MINUTES)
    sb = get_supabase_admin()
    try:
        sb.table("bookings").insert({
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "name": name,
            "email": email,
            "note": note or None,
            "visitor_timezone": body.visitor_timezone or None,
            "status": "confirmed",
        }).execute()
    except Exception as exc:  # unique-violation → slot taken between check & insert
        raise HTTPException(status_code=409, detail="That time was just taken") from exc

    booking = {
        "name": name, "email": email, "note": note,
        "when_label": _when_label(start, settings.BOOKING_TIMEZONE),
    }
    import logging
    log = logging.getLogger(__name__)
    for fn in (booking_email.send_host_notification, booking_email.send_visitor_confirmation):
        try:
            fn(booking=booking)
        except Exception:  # noqa: BLE001 — email is best-effort; row is the record
            log.exception("booking email failed (%s)", fn.__name__)

    return JSONResponse(content={"success": True, "start": start.isoformat(), "end": end.isoformat()})


@router.post("/cron/reminders")
async def send_reminders(request: Request) -> JSONResponse:
    secret = request.headers.get("x-cron-secret", "")
    if not settings.BOOKING_CRON_SECRET or secret != settings.BOOKING_CRON_SECRET:
        raise HTTPException(status_code=403, detail="Forbidden")

    now = datetime.now(UTC)
    window_end = now + timedelta(minutes=65)
    sb = get_supabase_admin()
    rows = (
        sb.table("bookings")
        .select("id, email, name, note, start_utc, visitor_timezone")
        .eq("status", "confirmed")
        .is_("reminder_sent_at", "null")
        .gte("start_utc", now.isoformat())
        .lte("start_utc", window_end.isoformat())
        .execute()
    )
    import logging
    log = logging.getLogger(__name__)
    sent = 0
    for b in rows.data or []:
        start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
        try:
            booking_reminder_email.send(
                to_email=b["email"], name=b["name"], note=b.get("note"),
                when_label=_when_label(start, b.get("visitor_timezone") or settings.BOOKING_TIMEZONE),
                meeting_url=settings.BOOKING_MEETING_URL,
            )
            sb.table("bookings").update({"reminder_sent_at": now.isoformat()}).eq("id", b["id"]).execute()
            sent += 1
        except Exception:  # noqa: BLE001
            log.exception("reminder failed for booking %s", b.get("id"))
    return JSONResponse(content={"sent": sent})
```

- [ ] **Step 3b: Fix the `/availability` endpoint**

Replace the placeholder `availability` function with the real one (FastAPI can't use `from` as a param name, so alias it):

```python
from fastapi import Query

@router.get("/availability")
def availability(
    from_: str = Query(..., alias="from"),
    to: str = Query(...),
) -> JSONResponse:
    tz = ZoneInfo(settings.BOOKING_TIMEZONE)
    today = datetime.now(UTC).astimezone(tz).date()
    horizon = today + timedelta(days=settings.BOOKING_HORIZON_DAYS)
    try:
        d0 = datetime.strptime(from_, "%Y-%m-%d").date()
        d1 = datetime.strptime(to, "%Y-%m-%d").date()
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad range") from exc
    days: list[str] = []
    cur = d0
    while cur <= d1:
        if (
            cur.isoweekday() in settings.booking_working_days
            and today <= cur <= horizon
        ):
            days.append(cur.isoformat())
        cur += timedelta(days=1)
    return JSONResponse(content={"days": days})
```

- [ ] **Step 4: Mount the router in `main.py`**

In `backend/auth_service/main.py`, add the import near the other router imports (line ~23):
```python
from .routers.booking import router as booking_router  # noqa: E402
```
And include it near the other `app.include_router(...)` calls (line ~140):
```python
app.include_router(booking_router)
```

- [ ] **Step 5: Run it — expect pass**

Run: `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_router.py -v`
Expected: 6 passed. Also run `python -c "import auth_service.main"` → no import error.

---

## Task 7: Reminder cron migration (pg_cron + pg_net)

**Files:** Create `backend/migrations/2026_06_03_booking_reminders_cron.sql`

- [ ] **Step 1: Write the migration**

```sql
-- backend/migrations/2026_06_03_booking_reminders_cron.sql
-- Fires the booking reminder endpoint every 5 minutes via pg_net.
-- The cron secret lives in Supabase Vault (created out-of-band, NOT in git):
--   select vault.create_secret('<random-secret>', 'booking_cron_secret');
-- and the SAME value is set as BOOKING_CRON_SECRET on the backend env.
create extension if not exists pg_cron;
create extension if not exists pg_net;

select cron.unschedule('send-booking-reminders')
where exists (select 1 from cron.job where jobname = 'send-booking-reminders');

select cron.schedule(
  'send-booking-reminders',
  '*/5 * * * *',
  $$
  select net.http_post(
    url := 'https://cms-backend-roman.vercel.app/booking/cron/reminders',
    headers := jsonb_build_object(
      'Content-Type', 'application/json',
      'X-Cron-Secret', (select decrypted_secret from vault.decrypted_secrets where name = 'booking_cron_secret')
    )
  );
  $$
);

select jobname, schedule from cron.job where jobname = 'send-booking-reminders';
```

- [ ] **Step 2: Operator pre-step (Vault secret) — runbook note**

Before applying, create the secret and set the backend env (documented in Task 14). The Vault row must exist or the cron sends an empty header → 403 (harmless, just no reminders).

- [ ] **Step 3: Apply via Supabase MCP**

Use `apply_migration` with name `2026_06_03_booking_reminders_cron`. Confirm with `execute_sql`:
```sql
select jobname, schedule from cron.job where jobname = 'send-booking-reminders';
```
Expected: one row, schedule `*/5 * * * *`.

---

## Task 8: Shared field styles + ContactForm update

**Files:** Create `frontend/src/components/ui/fieldStyles.ts`, Modify `frontend/src/components/contact/ContactForm.tsx`

- [ ] **Step 1: Create the shared styles**

```ts
// frontend/src/components/ui/fieldStyles.ts
/** Input/textarea classes shared by the contact form and the booking form. */
export const fieldBase =
  "w-full rounded-[10px] border bg-surface/40 px-4 py-3 text-sm text-text-primary outline-none transition-colors placeholder:text-text-tertiary focus:bg-surface";
export const fieldOk = "border-border focus:border-accent/60";
export const fieldErr = "border-red-500/70 focus:border-red-500";
```

- [ ] **Step 2: Update ContactForm to import them**

In `frontend/src/components/contact/ContactForm.tsx`, delete the three local `const fieldBase/fieldOk/fieldErr` declarations and add to the imports:
```tsx
import { fieldBase, fieldOk, fieldErr } from "@/components/ui/fieldStyles";
```

- [ ] **Step 3: Typecheck**

Run (from `frontend/`): `npx tsc --noEmit` → no errors in `ContactForm.tsx` / `fieldStyles.ts`.

---

## Task 9: Date helpers + MonthGrid

**Files:** Create `frontend/src/lib/bookingDates.ts`, `frontend/src/components/booking/MonthGrid.tsx`

- [ ] **Step 1: Create date helpers**

```ts
// frontend/src/lib/bookingDates.ts
/** YYYY-MM-DD key in *local* time (matches the host-day strings the API returns). */
export function dateKey(d: Date): string {
  const y = d.getFullYear();
  const m = String(d.getMonth() + 1).padStart(2, "0");
  const day = String(d.getDate()).padStart(2, "0");
  return `${y}-${m}-${day}`;
}

/** Weeks (Mon-first) covering the given month, including spill days. */
export function monthMatrix(year: number, month: number): Date[][] {
  const first = new Date(year, month, 1);
  const startOffset = (first.getDay() + 6) % 7; // 0=Mon
  const gridStart = new Date(year, month, 1 - startOffset);
  const weeks: Date[][] = [];
  const cur = new Date(gridStart);
  for (let w = 0; w < 6; w++) {
    const row: Date[] = [];
    for (let i = 0; i < 7; i++) {
      row.push(new Date(cur));
      cur.setDate(cur.getDate() + 1);
    }
    weeks.push(row);
  }
  return weeks;
}

export const MONTH_LABELS = [
  "January", "February", "March", "April", "May", "June",
  "July", "August", "September", "October", "November", "December",
];
export const WEEKDAY_LABELS = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"];
```

- [ ] **Step 2: Create MonthGrid**

```tsx
// frontend/src/components/booking/MonthGrid.tsx
"use client";

import { m } from "motion/react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { cn } from "@/lib/utils";
import { dateKey, monthMatrix, MONTH_LABELS, WEEKDAY_LABELS } from "@/lib/bookingDates";

interface MonthGridProps {
  viewYear: number;
  viewMonth: number; // 0-11
  bookableDays: Set<string>; // YYYY-MM-DD
  loading: boolean;
  onPrevMonth: () => void;
  onNextMonth: () => void;
  onSelectDay: (d: Date) => void;
}

export function MonthGrid({
  viewYear, viewMonth, bookableDays, loading, onPrevMonth, onNextMonth, onSelectDay,
}: MonthGridProps) {
  const weeks = monthMatrix(viewYear, viewMonth);
  return (
    <div>
      <div className="mb-4 flex items-center justify-between">
        <button
          type="button"
          onClick={onPrevMonth}
          aria-label="Previous month"
          className="rounded-lg border border-border p-1.5 text-text-secondary outline-none transition-colors hover:border-accent/50 hover:text-accent focus-visible:border-accent"
        >
          <ChevronLeft className="h-4 w-4" />
        </button>
        <p className="font-display text-sm font-semibold text-text-primary">
          {MONTH_LABELS[viewMonth]} {viewYear}
        </p>
        <button
          type="button"
          onClick={onNextMonth}
          aria-label="Next month"
          className="rounded-lg border border-border p-1.5 text-text-secondary outline-none transition-colors hover:border-accent/50 hover:text-accent focus-visible:border-accent"
        >
          <ChevronRight className="h-4 w-4" />
        </button>
      </div>

      <div className="grid grid-cols-7 gap-1 text-center">
        {WEEKDAY_LABELS.map((d) => (
          <div key={d} className="pb-2 text-xs font-medium text-text-tertiary">{d}</div>
        ))}
        {weeks.flat().map((day) => {
          const key = dateKey(day);
          const inMonth = day.getMonth() === viewMonth;
          const bookable = inMonth && bookableDays.has(key);
          return (
            <button
              key={key}
              type="button"
              disabled={!bookable || loading}
              onClick={() => onSelectDay(day)}
              className={cn(
                "flex h-10 items-center justify-center rounded-lg text-sm outline-none transition-colors",
                !inMonth && "text-text-tertiary/30",
                inMonth && !bookable && "text-text-tertiary/50",
                bookable &&
                  "text-text-primary hover:bg-accent hover:text-bg focus-visible:bg-accent focus-visible:text-bg",
              )}
            >
              {day.getDate()}
            </button>
          );
        })}
      </div>
      {loading && (
        <m.p
          initial={{ opacity: 0 }} animate={{ opacity: 1 }}
          className="mt-3 text-center text-xs text-text-tertiary"
        >
          Loading availability…
        </m.p>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Typecheck** — `npx tsc --noEmit` → no errors in the new files.

---

## Task 10: TimeSlots + BookingDetailsForm

**Files:** Create `frontend/src/components/booking/TimeSlots.tsx`, `frontend/src/components/booking/BookingDetailsForm.tsx`

- [ ] **Step 1: TimeSlots**

```tsx
// frontend/src/components/booking/TimeSlots.tsx
"use client";

import { ChevronLeft } from "lucide-react";
import { cn } from "@/lib/utils";

interface TimeSlotsProps {
  dayLabel: string;
  tzLabel: string;
  slots: string[]; // UTC ISO
  loading: boolean;
  visitorTz: string;
  onBack: () => void;
  onPick: (iso: string) => void;
}

function formatTime(iso: string, tz: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit", minute: "2-digit", timeZone: tz,
  }).format(new Date(iso));
}

export function TimeSlots({
  dayLabel, tzLabel, slots, loading, visitorTz, onBack, onPick,
}: TimeSlotsProps) {
  return (
    <div>
      <button
        type="button"
        onClick={onBack}
        className="mb-3 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
      >
        <ChevronLeft className="h-4 w-4" /> Back
      </button>
      <p className="font-display text-sm font-semibold text-text-primary">{dayLabel}</p>
      <p className="mb-3 text-xs text-text-tertiary">Times in {tzLabel}</p>

      {loading ? (
        <p className="py-8 text-center text-sm text-text-tertiary">Loading times…</p>
      ) : slots.length === 0 ? (
        <p className="py-8 text-center text-sm text-text-tertiary">No times available this day.</p>
      ) : (
        <div className="no-scrollbar max-h-[320px] space-y-2 overflow-y-auto pr-1">
          {slots.map((iso) => (
            <button
              key={iso}
              type="button"
              onClick={() => onPick(iso)}
              className={cn(
                "w-full rounded-[10px] border border-border bg-surface/40 px-4 py-3 text-sm font-medium text-text-primary outline-none transition-colors",
                "hover:border-accent/60 hover:bg-surface focus-visible:border-accent",
              )}
            >
              {formatTime(iso, visitorTz)}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: BookingDetailsForm**

```tsx
// frontend/src/components/booking/BookingDetailsForm.tsx
"use client";

import { useState } from "react";
import { ChevronLeft, CalendarCheck } from "lucide-react";
import { HeroButton } from "@/components/ui/HeroButton";
import { fieldBase, fieldOk, fieldErr } from "@/components/ui/fieldStyles";
import { cn } from "@/lib/utils";

const EMAIL_RE = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export interface BookingDetails {
  name: string;
  email: string;
  note: string;
  website: string; // honeypot
}

interface Props {
  slotLabel: string;
  onBack: () => void;
  onSubmit: (d: BookingDetails) => void;
}

export function BookingDetailsForm({ slotLabel, onBack, onSubmit }: Props) {
  const [values, setValues] = useState<BookingDetails>({ name: "", email: "", note: "", website: "" });
  const [errors, setErrors] = useState<{ name?: string; email?: string }>({});

  function update<K extends keyof BookingDetails>(key: K) {
    return (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
      setValues((v) => ({ ...v, [key]: e.target.value }));
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const next: typeof errors = {};
    if (!values.name.trim()) next.name = "Please add your name.";
    if (!EMAIL_RE.test(values.email.trim())) next.email = "That email does not look right.";
    setErrors(next);
    if (Object.keys(next).length === 0) onSubmit(values);
  }

  return (
    <form noValidate onSubmit={handleSubmit} className="space-y-4">
      <button
        type="button"
        onClick={onBack}
        className="inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
      >
        <ChevronLeft className="h-4 w-4" /> Back
      </button>
      <p className="font-display text-sm font-semibold text-accent">{slotLabel}</p>

      <div>
        <label htmlFor="booking-name" className="mb-1.5 block text-sm font-medium text-text-secondary">
          Name <span className="text-accent">*</span>
        </label>
        <input
          id="booking-name" type="text" autoComplete="name"
          value={values.name} onChange={update("name")}
          className={cn(fieldBase, errors.name ? fieldErr : fieldOk)} placeholder="Jane Doe"
        />
        {errors.name && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.name}</p>}
      </div>

      <div>
        <label htmlFor="booking-email" className="mb-1.5 block text-sm font-medium text-text-secondary">
          Email <span className="text-accent">*</span>
        </label>
        <input
          id="booking-email" type="email" autoComplete="email"
          value={values.email} onChange={update("email")}
          className={cn(fieldBase, errors.email ? fieldErr : fieldOk)} placeholder="jane@company.com"
        />
        {errors.email && <p role="alert" className="mt-1.5 text-xs text-red-400">{errors.email}</p>}
      </div>

      <div>
        <label htmlFor="booking-note" className="mb-1.5 block text-sm font-medium text-text-secondary">
          What would you like to discuss? <span className="text-text-tertiary">(optional)</span>
        </label>
        <textarea
          id="booking-note" rows={3} value={values.note} onChange={update("note")}
          className={cn(fieldBase, "resize-y", fieldOk)} placeholder="A sentence or two of context."
        />
      </div>

      {/* Honeypot — visually hidden, not announced to AT. */}
      <input
        type="text" tabIndex={-1} autoComplete="off" aria-hidden="true"
        value={values.website} onChange={update("website")}
        className="absolute left-[-9999px] h-0 w-0 opacity-0" name="website"
      />

      <HeroButton type="submit" variant="primary" className="w-full">
        <CalendarCheck className="h-4 w-4" aria-hidden={true} /> Schedule
      </HeroButton>
    </form>
  );
}
```

- [ ] **Step 3: Typecheck** — `npx tsc --noEmit` → no errors in the new files.

---

## Task 11: BookingConfirmation + BookingCalendar orchestrator

**Files:** Create `frontend/src/components/booking/BookingConfirmation.tsx`, `frontend/src/components/booking/BookingCalendar.tsx`

- [ ] **Step 1: BookingConfirmation**

```tsx
// frontend/src/components/booking/BookingConfirmation.tsx
"use client";

import { m } from "motion/react";
import { SubmitFeedback, type SubmitStatus } from "@/components/ui/SubmitFeedback";

const EXPO = [0.16, 1, 0.3, 1] as const;

interface Props {
  status: SubmitStatus;
  slotLabel: string;
  recipient: string;
  onReset: () => void;
}

export function BookingConfirmation({ status, slotLabel, recipient, onReset }: Props) {
  return (
    <div>
      <SubmitFeedback
        status={status}
        loadingText="Booking your call…"
        successText="You're booked — check your email!"
        errorText={
          <>
            Could not book that slot. Email me directly at{" "}
            <a href={`mailto:${recipient}`} className="text-accent underline-offset-2 hover:underline">
              {recipient}
            </a>
            .
          </>
        }
      />
      {status === "success" && (
        <m.p
          initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }}
          transition={{ duration: 0.4, ease: EXPO, delay: 0.2 }}
          className="text-center text-sm text-text-secondary"
        >
          {slotLabel}
        </m.p>
      )}
      {status !== "loading" && (
        <div className="mt-4 text-center">
          <button
            type="button" onClick={onReset}
            className="text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-accent focus-visible:underline"
          >
            {status === "success" ? "Book another time" : "Try again"}
          </button>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 2: BookingCalendar orchestrator**

```tsx
// frontend/src/components/booking/BookingCalendar.tsx
"use client";

import { useCallback, useEffect, useState } from "react";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { dateKey } from "@/lib/bookingDates";
import { MonthGrid } from "@/components/booking/MonthGrid";
import { TimeSlots } from "@/components/booking/TimeSlots";
import { BookingDetailsForm, type BookingDetails } from "@/components/booking/BookingDetailsForm";
import { BookingConfirmation } from "@/components/booking/BookingConfirmation";
import { cn } from "@/lib/utils";

const EXPO = [0.16, 1, 0.3, 1] as const;
const MIN_SPINNER_MS = 700;
const sleep = (ms: number) => new Promise((r) => setTimeout(r, ms));

type Step = "date" | "time" | "details" | "done";
type Phase = "loading" | "success" | "error";

const visitorTz = () =>
  typeof Intl !== "undefined" ? Intl.DateTimeFormat().resolvedOptions().timeZone : "UTC";

function monthRange(y: number, m: number): { from: string; to: string } {
  const from = dateKey(new Date(y, m, 1));
  const to = dateKey(new Date(y, m + 1, 0));
  return { from, to };
}

export function BookingCalendar({ recipient }: { recipient: string }) {
  const now = new Date();
  const [step, setStep] = useState<Step>("date");
  const [viewYear, setViewYear] = useState(now.getFullYear());
  const [viewMonth, setViewMonth] = useState(now.getMonth());
  const [bookableDays, setBookableDays] = useState<Set<string>>(new Set());
  const [daysLoading, setDaysLoading] = useState(false);
  const [selectedDay, setSelectedDay] = useState<Date | null>(null);
  const [slots, setSlots] = useState<string[]>([]);
  const [slotsLoading, setSlotsLoading] = useState(false);
  const [selectedSlot, setSelectedSlot] = useState<string | null>(null);
  const [phase, setPhase] = useState<Phase>("loading");

  const tz = visitorTz();

  const loadDays = useCallback(async (y: number, m: number) => {
    setDaysLoading(true);
    try {
      const { from, to } = monthRange(y, m);
      const res = await fetch(`/api/booking/availability?from=${from}&to=${to}`);
      const data = (await res.json()) as { days?: string[] };
      setBookableDays(new Set(data.days ?? []));
    } catch {
      setBookableDays(new Set());
    } finally {
      setDaysLoading(false);
    }
  }, []);

  useEffect(() => { void loadDays(viewYear, viewMonth); }, [viewYear, viewMonth, loadDays]);

  function changeMonth(delta: number) {
    const d = new Date(viewYear, viewMonth + delta, 1);
    setViewYear(d.getFullYear());
    setViewMonth(d.getMonth());
  }

  async function pickDay(day: Date) {
    setSelectedDay(day);
    setStep("time");
    setSlotsLoading(true);
    try {
      const res = await fetch(`/api/booking/slots?date=${dateKey(day)}&tz=${encodeURIComponent(tz)}`);
      const data = (await res.json()) as { slots?: string[] };
      setSlots(data.slots ?? []);
    } catch {
      setSlots([]);
    } finally {
      setSlotsLoading(false);
    }
  }

  function pickSlot(iso: string) {
    setSelectedSlot(iso);
    setStep("details");
  }

  async function submit(details: BookingDetails) {
    if (!selectedSlot) return;
    setPhase("loading");
    setStep("done");
    try {
      const [res] = await Promise.all([
        fetch("/api/booking", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            slot_start: selectedSlot,
            name: details.name.trim(),
            email: details.email.trim(),
            note: details.note.trim(),
            visitor_timezone: tz,
            website: details.website,
          }),
        }),
        sleep(MIN_SPINNER_MS),
      ]);
      const data = (await res.json()) as { success?: boolean };
      if (!res.ok || !data?.success) throw new Error("failed");
      setPhase("success");
    } catch {
      setPhase("error");
    }
  }

  function reset(toStart: boolean) {
    setPhase("loading");
    setSelectedSlot(null);
    if (toStart) { setSelectedDay(null); setStep("date"); }
    else { setStep("details"); }
  }

  const dayLabel = selectedDay
    ? new Intl.DateTimeFormat(undefined, { weekday: "long", day: "numeric", month: "long", timeZone: tz }).format(selectedDay)
    : "";
  const slotLabel = selectedSlot
    ? new Intl.DateTimeFormat(undefined, { weekday: "short", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit", timeZone: tz }).format(new Date(selectedSlot))
    : "";

  return (
    <LazyMotion features={domAnimation}>
      <MotionConfig reducedMotion="user">
        <div className={cn("rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8")}>
          <AnimatePresence mode="wait" initial={false}>
            <m.div
              key={step}
              initial={{ opacity: 0, x: 24 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -24 }}
              transition={{ duration: 0.35, ease: EXPO }}
            >
              {step === "date" && (
                <MonthGrid
                  viewYear={viewYear} viewMonth={viewMonth}
                  bookableDays={bookableDays} loading={daysLoading}
                  onPrevMonth={() => changeMonth(-1)} onNextMonth={() => changeMonth(1)}
                  onSelectDay={pickDay}
                />
              )}
              {step === "time" && (
                <TimeSlots
                  dayLabel={dayLabel} tzLabel={tz} slots={slots} loading={slotsLoading}
                  visitorTz={tz} onBack={() => setStep("date")} onPick={pickSlot}
                />
              )}
              {step === "details" && (
                <BookingDetailsForm slotLabel={slotLabel} onBack={() => setStep("time")} onSubmit={submit} />
              )}
              {step === "done" && (
                <BookingConfirmation status={phase} slotLabel={slotLabel} recipient={recipient} onReset={() => reset(phase === "success")} />
              )}
            </m.div>
          </AnimatePresence>
        </div>
      </MotionConfig>
    </LazyMotion>
  );
}
```

- [ ] **Step 3: Typecheck** — `npx tsc --noEmit` → no errors in the new files.

---

## Task 12: Wire into ContactSection + remove Calendly

**Files:** Modify `frontend/src/components/contact/ContactSection.tsx`, Delete `frontend/src/components/contact/CalendlyCalendar.tsx`, Modify `frontend/package.json`, `frontend/next.config.ts`

- [ ] **Step 1: Swap the component in ContactSection**

In `ContactSection.tsx`, replace the import
`import { CalendlyCalendar } from "@/components/contact/CalendlyCalendar";`
with
`import { BookingCalendar } from "@/components/booking/BookingCalendar";`
and replace `<CalendlyCalendar />` with `<BookingCalendar recipient={recipient} />` (the `recipient` const already exists in that file).

- [ ] **Step 2: Delete the Calendly component**

```bash
rm "frontend/src/components/contact/CalendlyCalendar.tsx"
```

- [ ] **Step 3: Remove the dependency**

Run (from `frontend/`): `npm uninstall react-calendly` (updates `package.json` + lockfile).

- [ ] **Step 4: Remove Calendly from the CSP**

In `frontend/next.config.ts`, revert the three Calendly additions:
```
"script-src 'self' 'unsafe-inline' 'unsafe-eval'",
"style-src 'self' 'unsafe-inline' https://fonts.googleapis.com",
```
and
```
// Embedded video providers used by the CMS VideoEditor only.
"frame-src https://www.youtube.com https://player.vimeo.com",
```

- [ ] **Step 5: Typecheck** — `npx tsc --noEmit` → no references to `CalendlyCalendar` / `react-calendly` remain.

---

## Task 13: Verification milestone

- [ ] **Step 1: Backend tests**

Run (from `backend/`): `source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_availability.py auth_service/tests/test_booking_email.py auth_service/tests/test_booking_reminder_email.py auth_service/tests/test_booking_router.py -v`
Expected: all green.

- [ ] **Step 2: Frontend typecheck + build**

Run (from `frontend/`): `npx tsc --noEmit` then `npm run build`.
Expected: clean typecheck; build succeeds; `/` prerenders.

- [ ] **Step 3: Manual smoke (servers running)**

With backend on :8001 and `npm run dev`, set `BOOKING_MEETING_URL` + a real `RESEND_API_KEY` in `backend/.env`:
- Home page → contact section: the booking calendar renders, future weekdays selectable, weekends/past greyed.
- Pick a day → slots load in your local tz; pick a slot → details form (note optional) → Schedule → spinner → gold checkmark.
- Confirm the email lands at `stefanromanpers@gmail.com` and the visitor email carries the standing link.

---

## Task 14: Operator runbook (env + secret)

**Files:** none (configuration); document in the PR description.

- [ ] **Step 1: Backend env (both `backend/.env` and Vercel `cms-backend-roman`)**

```
BOOKING_MEETING_URL=<your standing Google Meet or Zoom personal link>
BOOKING_CRON_SECRET=<random long string>
```
(The other `BOOKING_*` settings have sensible defaults; override only to change hours/timezone/duration.)

- [ ] **Step 2: Supabase Vault secret (matches BOOKING_CRON_SECRET)**

In the Supabase SQL editor (one-time, value NOT committed):
```sql
select vault.create_secret('<same value as BOOKING_CRON_SECRET>', 'booking_cron_secret');
```

- [ ] **Step 3: Restart the backend** so the new env loads (`uvicorn` reads `.env` at startup).

---

## Commit (only when Stefan says so)

Per project convention, no auto-commits. When approved, stage all created/modified files (backend services/router/tests/migrations, frontend booking components, ContactSection, next.config, package files) plus the spec + this plan, and commit:
```bash
git commit -m "feat(booking): custom Supabase-backed booking widget replacing Calendly"
```

---

## Self-Review

**Spec coverage:**
- 4-step custom UI w/ Motion transitions → Tasks 9–11 (AnimatePresence keyed by `step`). ✅
- Contact-form-matched fields + `HeroButton` "Schedule" + `SubmitFeedback` confirm → Tasks 8, 10, 11. ✅
- Hidden scrollbar on time list → Task 10 (`.no-scrollbar`). ✅
- Visitor-tz times → Tasks 10/11 (`Intl.DateTimeFormat`). ✅
- Fields Name*/Email*/Note(optional) → Task 10. ✅
- Store booking + prevent double-book → Tasks 1, 6 (partial unique index + `_slot_is_free`). ✅
- Host email + visitor email (standing link) → Tasks 4, 6. ✅
- ~1h reminder via pg_cron+pg_net+Vault, header cloned → Tasks 5, 6, 7. ✅
- 120-day horizon, 2h min notice, 45 min, Mon–Fri 9–18 EET → Tasks 2, 3. ✅
- Abuse: honeypot + rate-limit → Tasks 6, 10. ✅
- Calendly removal (component, dep, CSP) → Task 12. ✅
- Standing link config + acceptance email to Stefan → Tasks 2, 4, 6, 14. ✅

**Placeholder scan:** The only intentional throwaway is the `/availability` stub in Task 6 Step 3, explicitly replaced in Step 3b — flagged, not a gap. No other TBDs.

**Type consistency:** `available_slot_starts(**_slot_kwargs(), booked_starts_utc=...)` matches the service signature; `BookingRequest` fields match the frontend POST body and the table columns; `SubmitStatus` ("loading"|"success"|"error") matches `BookingConfirmation`'s `Phase` mapping; `dateKey`/`monthMatrix` signatures match their MonthGrid usage; `booking_email.send_host_notification(booking=...)` / `send_visitor_confirmation(booking=...)` match the router calls and the test patches.
```
