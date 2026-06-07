# Client Cancel / Reschedule Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a client cancel (≤24h before) or reschedule (≤12h before, max 2 times) their booked call from a secure link in their emails — deleting/moving the Google Calendar event and emailing both parties.

**Architecture:** Two new `bookings` columns (`manage_token`, `google_event_id`, plus `reschedule_count`); three token-authorized backend endpoints (`GET/POST/POST /booking/manage/{token}…`); Google Calendar `delete_event`/`update_event_time` over urllib; a branded `booking_manage_email` module; a frontend `/manage/[token]` page that reuses `BookingCalendar` in a new "reschedule" mode.

**Tech Stack:** FastAPI + Python 3.13 (`secrets`, `urllib`), Supabase, Resend, Next.js 16 + `motion/react`.

**Conventions:**
- `motion/react`, never `framer-motion`.
- **No auto-commit per task** (project rule) — implement all tasks, commit once when Stefan says so.
- Backend tests: from `backend/`, `source venv/Scripts/activate && python -m pytest <path> -v`.
- Migrations applied via the Supabase MCP `apply_migration` tool (project `xeluydwpgiddbamysgyu`), then saved under `backend/migrations/`.
- Backend booking router tests must stay **hermetic** — any test that reaches the booking/manage code paths must patch `google_calendar.*` so the real (configured) Google API is never called.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `backend/migrations/2026_06_04_bookings_manage.sql` | Create + apply | `manage_token`, `google_event_id`, `reschedule_count` columns + token index. |
| `backend/auth_service/core/config.py` | Modify | `BOOKING_PUBLIC_BASE_URL`, `BOOKING_MAX_RESCHEDULES`. |
| `backend/auth_service/services/google_calendar.py` | Modify | `delete_event`, `update_event_time`. |
| `backend/auth_service/services/booking_manage_email.py` | Create | Cancellation + reschedule emails (host + client). |
| `backend/auth_service/services/booking_email.py` | Modify | Add `manage_url` link to the visitor confirmation. |
| `backend/auth_service/services/booking_reminder_email.py` | Modify | Add `manage_url` link to the reminder. |
| `backend/auth_service/routers/booking.py` | Modify | Store token + event id on create; pass manage_url; 3 manage endpoints. |
| `backend/auth_service/tests/test_*` | Create/Modify | Unit tests. |
| `frontend/src/app/(marketing)/manage/[token]/page.tsx` | Create | Management page. |
| `frontend/src/components/booking/BookingCalendar.tsx` | Modify | `reschedule` mode. |

---

## Task 1: Migration — manage columns

**Files:** Create `backend/migrations/2026_06_04_bookings_manage.sql`

- [ ] **Step 1: Write the migration**

```sql
-- backend/migrations/2026_06_04_bookings_manage.sql
-- Client self-service cancel/reschedule: token-secured management links.
alter table public.bookings add column if not exists manage_token text;
alter table public.bookings add column if not exists google_event_id text;
alter table public.bookings add column if not exists reschedule_count int not null default 0;

create unique index if not exists bookings_manage_token_uniq
  on public.bookings (manage_token);
```

- [ ] **Step 2: Apply via Supabase MCP**

Use `apply_migration`, name `2026_06_04_bookings_manage`, project `xeluydwpgiddbamysgyu`. Verify:
```sql
select column_name from information_schema.columns
where table_name='bookings' and column_name in ('manage_token','google_event_id','reschedule_count');
```
Expected: 3 rows.

---

## Task 2: Config

**Files:** Modify `backend/auth_service/core/config.py`

- [ ] **Step 1: Add settings**

After the `GOOGLE_CALENDAR_ID` line in `class Settings`, add:
```python
    # Client self-service management
    BOOKING_PUBLIC_BASE_URL: str = "https://roman-technologies.dev"  # base for /manage/{token}
    BOOKING_MAX_RESCHEDULES: int = 2
```

- [ ] **Step 2: Verify**

Run: `source venv/Scripts/activate && python -c "from auth_service.core.config import settings; print(settings.BOOKING_PUBLIC_BASE_URL, settings.BOOKING_MAX_RESCHEDULES)"`
Expected: `https://roman-technologies.dev 2`

---

## Task 3: Google Calendar delete + move (TDD)

**Files:** Modify `backend/auth_service/services/google_calendar.py`, Test `backend/auth_service/tests/test_google_calendar.py`

- [ ] **Step 1: Append failing tests**

Append to `backend/auth_service/tests/test_google_calendar.py`:
```python
def test_delete_event_calls_delete():
    with patch("auth_service.services.google_calendar._api") as api:
        google_calendar.delete_event("evt1")
    assert api.call_args.args[0] == "DELETE"
    assert "evt1" in api.call_args.args[1]
    assert api.call_args.kwargs["params"]["sendUpdates"] == "none"


def test_delete_event_swallows_404():
    with patch(
        "auth_service.services.google_calendar._api",
        side_effect=RuntimeError("Google Calendar 404: not found"),
    ):
        google_calendar.delete_event("evt1")  # must NOT raise


def test_delete_event_reraises_other_errors():
    import pytest
    with patch(
        "auth_service.services.google_calendar._api",
        side_effect=RuntimeError("Google Calendar 500: boom"),
    ):
        with pytest.raises(RuntimeError):
            google_calendar.delete_event("evt1")


def test_update_event_time_patches_start_end():
    with patch("auth_service.services.google_calendar._api") as api:
        google_calendar.update_event_time(
            "evt1",
            datetime(2026, 6, 11, 8, 0, tzinfo=UTC),
            datetime(2026, 6, 11, 8, 45, tzinfo=UTC),
        )
    assert api.call_args.args[0] == "PATCH"
    assert "evt1" in api.call_args.args[1]
    body = api.call_args.kwargs["body"]
    assert body["start"]["dateTime"].startswith("2026-06-11T08:00")
    assert body["end"]["dateTime"].startswith("2026-06-11T08:45")
```

- [ ] **Step 2: Run — expect failure** (`delete_event`/`update_event_time` undefined).

- [ ] **Step 3: Implement** — append to `backend/auth_service/services/google_calendar.py`:
```python
def delete_event(event_id: str) -> None:
    """Remove the host-calendar event. A 404/410 (already gone) is ignored."""
    cal = urllib.parse.quote(settings.GOOGLE_CALENDAR_ID, safe="")
    eid = urllib.parse.quote(event_id, safe="")
    try:
        _api("DELETE", f"/calendars/{cal}/events/{eid}", params={"sendUpdates": "none"})
    except RuntimeError as exc:
        if "404" in str(exc) or "410" in str(exc):
            return
        raise


def update_event_time(event_id: str, start_utc: datetime, end_utc: datetime) -> None:
    """Move the host-calendar event to a new time (same Meet link / details)."""
    cal = urllib.parse.quote(settings.GOOGLE_CALENDAR_ID, safe="")
    eid = urllib.parse.quote(event_id, safe="")
    _api(
        "PATCH",
        f"/calendars/{cal}/events/{eid}",
        params={"sendUpdates": "none"},
        body={"start": {"dateTime": start_utc.isoformat()}, "end": {"dateTime": end_utc.isoformat()}},
    )
```

- [ ] **Step 4: Run — expect pass.**
`source venv/Scripts/activate && python -m pytest auth_service/tests/test_google_calendar.py -v` → all pass.

---

## Task 4: Cancellation / reschedule emails (TDD)

**Files:** Create `backend/auth_service/services/booking_manage_email.py`, Test `backend/auth_service/tests/test_booking_manage_email.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/auth_service/tests/test_booking_manage_email.py
from auth_service.services.booking_manage_email import (
    render_cancel_client,
    render_cancel_host,
    render_reschedule_client,
    render_reschedule_host,
)


def test_cancel_client_branded_and_escaped():
    h = render_cancel_client(name="<b>Jo</b>", when_label="Thu 11 Jun · 10:00 (CET)")
    assert "Roman Technologies" in h
    assert "cancel" in h.lower()
    assert "&lt;b&gt;Jo&lt;/b&gt;" in h
    assert "Thu 11 Jun · 10:00 (CET)" in h


def test_cancel_host_names_the_client():
    h = render_cancel_host(name="Jo", when_label="Thu 11 Jun · 11:00 (Europe/Bucharest)")
    assert "Jo" in h
    assert "Thu 11 Jun · 11:00 (Europe/Bucharest)" in h


def test_reschedule_client_shows_new_time_and_links():
    h = render_reschedule_client(
        name="Jo", new_when="Fri 12 Jun · 14:00 (CET)",
        meeting_url="https://meet.example/x", manage_url="https://site/manage/tok",
    )
    assert "Fri 12 Jun · 14:00 (CET)" in h
    assert "https://meet.example/x" in h
    assert "https://site/manage/tok" in h


def test_reschedule_host_shows_old_and_new():
    h = render_reschedule_host(
        name="Jo", old_when="Thu 11 Jun · 10:00", new_when="Fri 12 Jun · 14:00",
    )
    assert "Thu 11 Jun · 10:00" in h
    assert "Fri 12 Jun · 14:00" in h
```

- [ ] **Step 2: Run — expect ImportError.**

- [ ] **Step 3: Implement** `backend/auth_service/services/booking_manage_email.py`:
```python
"""Branded cancellation / reschedule emails (host + client). Mirrors
booking_email's Resend-over-urllib + E2E guard."""

from __future__ import annotations

import html
import json
import urllib.error
import urllib.request

from ..core.config import settings
from . import email_layout


def _box(rows: list[tuple[str, str]]) -> str:
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


def _heading(text: str) -> str:
    return (
        '<tr><td style="padding:32px 32px 8px">'
        f'<h1 style="margin:0;font-size:22px;font-weight:600;color:#18181b">{text}</h1></td></tr>'
    )


def _button(*, url: str, label: str) -> str:
    safe = email_layout.safe_url(url)
    if not safe:
        return ""
    return (
        '<tr><td style="padding:20px 32px 8px" align="center">'
        f'<a href="{html.escape(safe)}" style="display:inline-block;background:#18181b;color:#fff;'
        'text-decoration:none;font-size:14px;font-weight:600;padding:12px 28px;border-radius:8px">'
        f'{label} &rarr;</a></td></tr>'
    )


def render_cancel_client(*, name: str, when_label: str) -> str:
    inner = (
        email_layout.header("Booking cancelled")
        + _heading(f"Your call is cancelled, {html.escape(name)}.")
        + _box([("Was", html.escape(when_label))])
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def render_cancel_host(*, name: str, when_label: str) -> str:
    inner = (
        email_layout.header("Booking cancelled")
        + _heading("A call was cancelled")
        + _box([("Client", html.escape(name)), ("Was", html.escape(when_label))])
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def render_reschedule_client(*, name: str, new_when: str, meeting_url: str, manage_url: str) -> str:
    inner = (
        email_layout.header("Booking moved")
        + _heading(f"Your call is moved, {html.escape(name)}.")
        + _box([("New time", html.escape(new_when))])
        + _button(url=meeting_url, label="Join the call")
        + _button(url=manage_url, label="Manage your booking")
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def render_reschedule_host(*, name: str, old_when: str, new_when: str) -> str:
    inner = (
        email_layout.header("Booking moved")
        + _heading("A call was rescheduled")
        + _box([("Client", html.escape(name)), ("From", html.escape(old_when)), ("To", html.escape(new_when))])
        + email_layout.footer()
    )
    return email_layout.shell(inner)


def _send(*, to_email: str, subject: str, html_body: str, text_body: str) -> dict:
    from .e2e_email_guard import short_circuit_response, should_short_circuit

    if should_short_circuit(to_email, subject):
        return short_circuit_response(f"booking_manage:{to_email}")
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


def send_cancellation(*, name: str, client_email: str, host_when: str, client_when: str) -> None:
    _send(
        to_email=settings.BOOKING_HOST_EMAIL,
        subject=f"Cancelled — call with {name}",
        html_body=render_cancel_host(name=name, when_label=host_when),
        text_body=f"A call was cancelled.\nClient: {name}\nWas: {host_when}\n",
    )
    _send(
        to_email=client_email,
        subject="Your call with Stefan is cancelled",
        html_body=render_cancel_client(name=name, when_label=client_when),
        text_body=f"Your call is cancelled.\nWas: {client_when}\n",
    )


def send_reschedule(
    *, name: str, client_email: str, old_host_when: str, new_host_when: str,
    new_client_when: str, meeting_url: str, manage_url: str,
) -> None:
    _send(
        to_email=settings.BOOKING_HOST_EMAIL,
        subject=f"Rescheduled — call with {name}",
        html_body=render_reschedule_host(name=name, old_when=old_host_when, new_when=new_host_when),
        text_body=f"A call was rescheduled.\nClient: {name}\nFrom: {old_host_when}\nTo: {new_host_when}\n",
    )
    _send(
        to_email=client_email,
        subject="Your call with Stefan was moved",
        html_body=render_reschedule_client(
            name=name, new_when=new_client_when, meeting_url=meeting_url, manage_url=manage_url
        ),
        text_body=f"Your call is moved to {new_client_when}.\nJoin: {meeting_url}\nManage: {manage_url}\n",
    )
```

- [ ] **Step 4: Run — expect 4 pass.**

---

## Task 5: Store token/event-id on create + add manage link to client emails

**Files:** Modify `backend/auth_service/routers/booking.py`, `services/booking_email.py`, `services/booking_reminder_email.py`, Test `backend/auth_service/tests/test_booking_email.py`, `test_booking_router.py`

- [ ] **Step 1: Add `manage_url` to the visitor confirmation email**

In `booking_email.py`, change `render_visitor_html` + `send_visitor_confirmation` to accept and render a manage link. Replace the `render_visitor_html` signature and add the link after the `cta`:
```python
def render_visitor_html(*, booking: dict, meeting_url: str, manage_url: str = "") -> str:
    name = html.escape(booking["name"])
    when = html.escape(booking["when_label"])
    note = html.escape(booking.get("note") or "—").replace("\n", "<br>")
    cta = _cta_block(
        meeting_url=meeting_url,
        add_to_cal_url=_add_to_cal_url(
            booking=booking, meeting_url=meeting_url, title="Call with Stefan @ Roman Technologies"
        ),
    )
    manage = ""
    safe_manage = email_layout.safe_url(manage_url)
    if safe_manage:
        manage = (
            '<tr><td style="padding:8px 32px 0" align="center">'
            '<p style="margin:0;font-size:12px;color:#71717a">Need to change or cancel? '
            f'<a href="{html.escape(safe_manage)}" style="color:#52525b;text-decoration:underline">'
            'Manage your booking</a>.</p></td></tr>'
        )
    inner = (
        email_layout.header("Appointment confirmed")
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">You’re booked, {name}.</h1>'
        + '<p style="margin:0;font-size:15px;line-height:1.55;color:#52525b">Your call with Stefan is confirmed.</p></td></tr>'
        + _detail_box([("When", when), ("Note", note)])
        + cta
        + manage
        + email_layout.footer()
    )
    return email_layout.shell(inner)
```
And `send_visitor_confirmation`:
```python
def send_visitor_confirmation(*, booking: dict, meeting_url: str, manage_url: str = "") -> dict:
    link_line = (
        f"Join the call: {meeting_url}\n"
        if meeting_url
        else "Stefan will email you the link before the call.\n"
    )
    manage_line = f"Manage your booking: {manage_url}\n" if manage_url else ""
    text = (
        f"You're booked, {booking['name']}.\n\nWhen: {booking['when_label']}\n"
        f"Note: {booking.get('note') or '-'}\n{link_line}{manage_line}"
    )
    return _send(
        to_email=booking["email"],
        subject="Your call with Stefan is booked",
        html_body=render_visitor_html(booking=booking, meeting_url=meeting_url, manage_url=manage_url),
        text_body=text,
    )
```

- [ ] **Step 2: Add `manage_url` to the reminder email**

In `booking_reminder_email.py`, change `render_html` + `send` to accept `manage_url` and add a manage line. In `render_html`, after the `box`/`cta` composition add a manage paragraph; simplest — change the `send` signature and append to the box. Update `render_html` signature to `(*, name, when_label, note, meeting_url, manage_url="")` and add before the footer:
```python
    manage = ""
    safe_manage = email_layout.safe_url(manage_url)
    if safe_manage:
        manage = (
            '<tr><td style="padding:8px 32px 0" align="center">'
            '<p style="margin:0;font-size:12px;color:#71717a">Need to change or cancel? '
            f'<a href="{html.escape(safe_manage)}" style="color:#52525b;text-decoration:underline">'
            'Manage your booking</a>.</p></td></tr>'
        )
    inner = (
        email_layout.header("Appointment reminder")
        + f'<tr><td style="padding:32px 32px 8px"><h1 style="margin:0 0 12px;font-size:22px;font-weight:600;color:#18181b">Your call is in about an hour, {safe_name}.</h1></td></tr>'
        + box
        + cta
        + manage
        + email_layout.footer()
    )
```
And `send(*, to_email, name, when_label, note, meeting_url, manage_url="")` — pass `manage_url=manage_url` into `render_html(...)`.

- [ ] **Step 3: Store token + event id + pass manage_url in `create_booking`**

In `routers/booking.py`, add `import secrets` near the top imports. Then rewrite the insert/event/email block of `create_booking` (the section from `end = start + ...` through the two email sends) to:
```python
    end = start + timedelta(minutes=settings.BOOKING_SLOT_MINUTES)
    manage_token = secrets.token_urlsafe(32)
    sb = get_supabase_admin()
    try:
        res = sb.table("bookings").insert({
            "start_utc": start.isoformat(),
            "end_utc": end.isoformat(),
            "name": name,
            "email": email,
            "note": note or None,
            "visitor_timezone": body.visitor_timezone or None,
            "status": "confirmed",
            "manage_token": manage_token,
        }).execute()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "23505" in msg or "duplicate key" in msg:
            raise HTTPException(status_code=409, detail="That time was just taken") from exc
        log.exception("booking insert failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Booking could not be saved",
        ) from exc
    booking_id = (res.data or [{}])[0].get("id")

    if google_calendar.is_configured():
        try:
            event_id = google_calendar.create_event(
                start_utc=start, end_utc=end, name=name, email=email,
                note=note, meeting_url=settings.BOOKING_MEETING_URL,
            )
            if event_id and booking_id:
                sb.table("bookings").update({"google_event_id": event_id}).eq("id", booking_id).execute()
        except Exception:  # noqa: BLE001 — calendar sync is best-effort; the row is the record
            log.exception("google calendar event creation failed")

    meeting_url = settings.BOOKING_MEETING_URL
    manage_url = f"{settings.BOOKING_PUBLIC_BASE_URL}/manage/{manage_token}"
    base = {"name": name, "email": email, "note": note, "start_utc": start, "end_utc": end}
    host_booking = {**base, "when_label": _when_label(start, settings.BOOKING_TIMEZONE)}
    visitor_tz = body.visitor_timezone or settings.BOOKING_TIMEZONE
    visitor_booking = {**base, "when_label": _when_label(start, visitor_tz)}
    try:
        booking_email.send_host_notification(booking=host_booking, meeting_url=meeting_url)
    except Exception:  # noqa: BLE001
        log.exception("booking host email failed")
    try:
        booking_email.send_visitor_confirmation(
            booking=visitor_booking, meeting_url=meeting_url, manage_url=manage_url
        )
    except Exception:  # noqa: BLE001
        log.exception("booking visitor email failed")

    return JSONResponse(content={"success": True, "start": start.isoformat(), "end": end.isoformat()})
```

- [ ] **Step 4: Pass `manage_url` in the reminder cron**

In `send_reminders`, change the `.select(...)` to include `manage_token`, and pass `manage_url` to the reminder send:
```python
        .select("id, email, name, note, start_utc, visitor_timezone, manage_token")
```
and inside the loop:
```python
            booking_reminder_email.send(
                to_email=b["email"], name=b["name"], note=b.get("note"),
                when_label=_when_label(start, b.get("visitor_timezone") or settings.BOOKING_TIMEZONE),
                meeting_url=settings.BOOKING_MEETING_URL,
                manage_url=f"{settings.BOOKING_PUBLIC_BASE_URL}/manage/{b['manage_token']}" if b.get("manage_token") else "",
            )
```

- [ ] **Step 5: Update the booking-email test for the new signature**

In `test_booking_email.py`, add a test that the manage link renders, and that the existing visitor test still passes (the `manage_url` default is `""`). Append:
```python
def test_visitor_email_includes_manage_link_when_given():
    html = render_visitor_html(
        booking=BOOKING, meeting_url="https://meet.example/abc",
        manage_url="https://site/manage/tok123",
    )
    assert "Manage your booking" in html
    assert "https://site/manage/tok123" in html
```

- [ ] **Step 6: Update the router happy-path test for the new insert shape**

In `test_booking_router.py`, the `_sb_chain` already returns `data=[{"id":"b1"}]` for the happy path; the new `.update(...)` call after create_event also runs through the mock chain (returns the same mock) — fine. Confirm `test_booking_happy_path_inserts_and_emails` still passes (it patches `google_calendar.create_event`; with the patch returning a Mock, `event_id` is truthy → `.update()` is called on the mock — OK). No assertion change needed; just re-run.

- [ ] **Step 7: Run the affected suites**
`source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_email.py auth_service/tests/test_booking_reminder_email.py auth_service/tests/test_booking_router.py -v` → all pass; `python -c "import auth_service.main"` OK.

---

## Task 6: Manage endpoints (TDD)

**Files:** Modify `backend/auth_service/routers/booking.py`, Test `backend/auth_service/tests/test_booking_manage_router.py`

- [ ] **Step 1: Write failing tests**

```python
# backend/auth_service/tests/test_booking_manage_router.py
from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app


@pytest.fixture
def client():
    return TestClient(app)


def _row(**over):
    base = {
        "id": "b1", "manage_token": "tok", "status": "confirmed",
        "name": "Jo", "email": "jo@x.com", "visitor_timezone": "Europe/Berlin",
        "google_event_id": "evt1", "reschedule_count": 0,
        "start_utc": (datetime.now(UTC) + timedelta(days=3)).isoformat(),
        "end_utc": (datetime.now(UTC) + timedelta(days=3, minutes=45)).isoformat(),
    }
    base.update(over)
    return base


def _sb(row):
    sb = MagicMock()
    for m in ["table", "select", "eq", "limit", "update", "insert", "gte", "lte", "is_"]:
        getattr(sb, m).return_value = sb
    sb.execute.return_value = type("R", (), {"data": ([row] if row else [])})()
    return sb


def test_manage_get_flags(client):
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb(_row())):
        r = client.get("/booking/manage/tok")
    assert r.status_code == 200
    body = r.json()
    assert body["found"] is True
    assert body["can_cancel"] is True
    assert body["can_reschedule"] is True


def test_manage_get_not_found(client):
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb(None)):
        r = client.get("/booking/manage/nope")
    assert r.status_code == 200
    assert r.json()["found"] is False


def test_cancel_happy(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    sb = _sb(_row())
    with (
        patch("auth_service.routers.booking.get_supabase_admin", return_value=sb),
        patch("auth_service.routers.booking.google_calendar.is_configured", return_value=True),
        patch("auth_service.routers.booking.google_calendar.delete_event") as deln,
        patch("auth_service.routers.booking.booking_manage_email.send_cancellation") as mail,
    ):
        r = client.post("/booking/manage/tok/cancel")
    assert r.status_code == 200 and r.json()["success"] is True
    deln.assert_called_once()
    mail.assert_called_once()


def test_cancel_too_late(client):
    soon = _row(start_utc=(datetime.now(UTC) + timedelta(hours=5)).isoformat())
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb(soon)):
        r = client.post("/booking/manage/tok/cancel")
    assert r.status_code == 403


def test_cancel_already_cancelled(client):
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb(_row(status="cancelled"))):
        r = client.post("/booking/manage/tok/cancel")
    assert r.status_code == 409


def test_reschedule_happy(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    sb = _sb(_row())
    new_start = (datetime.now(UTC) + timedelta(days=4)).isoformat()
    with (
        patch("auth_service.routers.booking.get_supabase_admin", return_value=sb),
        patch("auth_service.routers.booking._slot_is_free", return_value=True),
        patch("auth_service.routers.booking.google_calendar.is_configured", return_value=True),
        patch("auth_service.routers.booking.google_calendar.update_event_time") as upd,
        patch("auth_service.routers.booking.booking_manage_email.send_reschedule") as mail,
    ):
        r = client.post("/booking/manage/tok/reschedule", json={"slot_start": new_start})
    assert r.status_code == 200 and r.json()["success"] is True
    upd.assert_called_once()
    mail.assert_called_once()


def test_reschedule_limit_reached(client):
    maxed = _row(reschedule_count=2)
    new_start = (datetime.now(UTC) + timedelta(days=4)).isoformat()
    with patch("auth_service.routers.booking.get_supabase_admin", return_value=_sb(maxed)):
        r = client.post("/booking/manage/tok/reschedule", json={"slot_start": new_start})
    assert r.status_code == 403
```

- [ ] **Step 2: Run — expect 404s/failures.**

- [ ] **Step 3: Implement the endpoints** — append to `backend/auth_service/routers/booking.py` (and add `from . import ... booking_manage_email` — extend the existing `from ..services import booking_email, booking_reminder_email, google_calendar` line to also import `booking_manage_email`):
```python
def _booking_by_token(token: str) -> dict | None:
    sb = get_supabase_admin()
    res = sb.table("bookings").select("*").eq("manage_token", token).limit(1).execute()
    rows = res.data or []
    return rows[0] if rows else None


@router.get("/manage/{token}")
def manage_get(token: str) -> JSONResponse:
    b = _booking_by_token(token)
    if not b:
        return JSONResponse(content={"found": False})
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    now = datetime.now(UTC)
    confirmed = b["status"] == "confirmed"
    count = b.get("reschedule_count") or 0
    return JSONResponse(content={
        "found": True,
        "status": b["status"],
        "start_utc": b["start_utc"],
        "end_utc": b["end_utc"],
        "name": b["name"],
        "visitor_timezone": b.get("visitor_timezone") or settings.BOOKING_TIMEZONE,
        "reschedule_count": count,
        "max_reschedules": settings.BOOKING_MAX_RESCHEDULES,
        "can_cancel": confirmed and now <= start - timedelta(hours=24),
        "can_reschedule": (
            confirmed and now <= start - timedelta(hours=12)
            and count < settings.BOOKING_MAX_RESCHEDULES
        ),
    })


@router.post("/manage/{token}/cancel")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_cancel(request: Request, token: str) -> JSONResponse:
    b = _booking_by_token(token)
    if not b:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    if datetime.now(UTC) > start - timedelta(hours=24):
        raise HTTPException(status_code=403, detail="Too late to cancel online")

    if b.get("google_event_id") and google_calendar.is_configured():
        try:
            google_calendar.delete_event(b["google_event_id"])
        except Exception:  # noqa: BLE001
            log.exception("google delete failed for booking %s", b["id"])

    get_supabase_admin().table("bookings").update({"status": "cancelled"}).eq("id", b["id"]).execute()

    tz = b.get("visitor_timezone") or settings.BOOKING_TIMEZONE
    try:
        booking_manage_email.send_cancellation(
            name=b["name"], client_email=b["email"],
            host_when=_when_label(start, settings.BOOKING_TIMEZONE),
            client_when=_when_label(start, tz),
        )
    except Exception:  # noqa: BLE001
        log.exception("cancellation email failed")
    return JSONResponse(content={"success": True})


class RescheduleRequest(BaseModel):
    slot_start: str


@router.post("/manage/{token}/reschedule")
@limiter.limit("10/hour", key_func=client_ip)
async def manage_reschedule(request: Request, token: str, body: RescheduleRequest) -> JSONResponse:
    b = _booking_by_token(token)
    if not b:
        raise HTTPException(status_code=404, detail="Not found")
    if b["status"] != "confirmed":
        raise HTTPException(status_code=409, detail="Already cancelled")
    old_start = datetime.fromisoformat(b["start_utc"]).astimezone(_UTC)
    if datetime.now(UTC) > old_start - timedelta(hours=12):
        raise HTTPException(status_code=403, detail="Too late to reschedule online")
    if (b.get("reschedule_count") or 0) >= settings.BOOKING_MAX_RESCHEDULES:
        raise HTTPException(status_code=403, detail="Reschedule limit reached")
    try:
        new_start = datetime.fromisoformat(body.slot_start).astimezone(_UTC)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail="Bad slot_start") from exc
    if not _slot_is_free(new_start):
        raise HTTPException(status_code=409, detail="That time was just taken")

    new_end = new_start + timedelta(minutes=settings.BOOKING_SLOT_MINUTES)
    sb = get_supabase_admin()
    try:
        sb.table("bookings").update({
            "start_utc": new_start.isoformat(),
            "end_utc": new_end.isoformat(),
            "reschedule_count": (b.get("reschedule_count") or 0) + 1,
        }).eq("id", b["id"]).execute()
    except Exception as exc:  # noqa: BLE001
        msg = str(exc).lower()
        if "23505" in msg or "duplicate key" in msg:
            raise HTTPException(status_code=409, detail="That time was just taken") from exc
        log.exception("reschedule update failed")
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Could not reschedule") from exc

    if b.get("google_event_id") and google_calendar.is_configured():
        try:
            google_calendar.update_event_time(b["google_event_id"], new_start, new_end)
        except Exception:  # noqa: BLE001
            log.exception("google patch failed for booking %s", b["id"])

    tz = b.get("visitor_timezone") or settings.BOOKING_TIMEZONE
    manage_url = f"{settings.BOOKING_PUBLIC_BASE_URL}/manage/{token}"
    try:
        booking_manage_email.send_reschedule(
            name=b["name"], client_email=b["email"],
            old_host_when=_when_label(old_start, settings.BOOKING_TIMEZONE),
            new_host_when=_when_label(new_start, settings.BOOKING_TIMEZONE),
            new_client_when=_when_label(new_start, tz),
            meeting_url=settings.BOOKING_MEETING_URL, manage_url=manage_url,
        )
    except Exception:  # noqa: BLE001
        log.exception("reschedule email failed")
    return JSONResponse(content={"success": True, "start": new_start.isoformat(), "end": new_end.isoformat()})
```

- [ ] **Step 4: Run — expect all pass.**
`source venv/Scripts/activate && python -m pytest auth_service/tests/test_booking_manage_router.py -v` → all pass. Also re-run the full booking suite to confirm no regressions.

---

## Task 7: `BookingCalendar` reschedule mode

**Files:** Modify `frontend/src/components/booking/BookingCalendar.tsx`

- [ ] **Step 1: Add a `reschedule` prop + confirm step**

Change the component signature and step machine. Replace the props line and add reschedule handling:

1. Update the type + signature:
```tsx
type Step = "date" | "time" | "confirm" | "details" | "done";

export function BookingCalendar({
  recipient,
  reschedule,
}: {
  recipient: string;
  reschedule?: { token: string; onDone?: () => void };
}) {
```

2. In `pickSlot`, branch on mode:
```tsx
  function pickSlot(iso: string) {
    setSelectedSlot(iso);
    setStep(reschedule ? "confirm" : "details");
  }
```

3. Add the reschedule submit + a confirm renderer. Add this function alongside `submit`:
```tsx
  async function submitReschedule() {
    if (!selectedSlot || !reschedule) return;
    setPhase("loading");
    setStep("done");
    try {
      const [res] = await Promise.all([
        fetch(`/api/booking/manage/${reschedule.token}/reschedule`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ slot_start: selectedSlot }),
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
```

4. Render the `confirm` step inside the `AnimatePresence` (add a new branch after the `time` step):
```tsx
              {step === "confirm" && (
                <div className="text-center">
                  <button
                    type="button"
                    onClick={() => setStep("time")}
                    className="mb-4 inline-flex items-center gap-1 text-sm text-text-secondary outline-none transition-colors hover:text-accent focus-visible:text-accent"
                  >
                    Back
                  </button>
                  <p className="mb-1 text-sm text-text-secondary">Move your call to</p>
                  <p className="mb-6 font-display text-lg font-semibold text-accent">{slotLabel}</p>
                  <HeroButton type="button" variant="primary" className="w-full" onClick={submitReschedule}>
                    Confirm new time
                  </HeroButton>
                </div>
              )}
```

5. In the `done` step, when in reschedule mode call `reschedule.onDone` on reset. Change the `done` branch's `onReset`:
```tsx
              {step === "done" && (
                <BookingConfirmation
                  status={phase}
                  slotLabel={slotLabel}
                  recipient={recipient}
                  onReset={() => {
                    if (reschedule && phase === "success") { reschedule.onDone?.(); return; }
                    reset(phase === "success");
                  }}
                />
              )}
```

6. Add the `HeroButton` import: `import { HeroButton } from "@/components/ui/HeroButton";`

7. The header text adapts: change the heading line to
```tsx
              <p className="font-display text-lg font-semibold text-text-primary">
                {reschedule ? "Reschedule your call" : "Book a call with Stefan"}
              </p>
```

- [ ] **Step 2: Typecheck** — from `frontend/`, `npx tsc --noEmit` → no errors in `BookingCalendar.tsx`. (Booking mode unchanged; reschedule adds the `confirm` step.)

---

## Task 8: Manage page

**Files:** Create `frontend/src/app/(marketing)/manage/[token]/page.tsx`

- [ ] **Step 1: Create the page**

```tsx
"use client";

import { use, useCallback, useEffect, useState } from "react";
import { LazyMotion, domAnimation, MotionConfig, AnimatePresence, m } from "motion/react";
import { HeroButton } from "@/components/ui/HeroButton";
import { SubmitFeedback, type SubmitStatus } from "@/components/ui/SubmitFeedback";
import { BookingCalendar } from "@/components/booking/BookingCalendar";

const EXPO = [0.16, 1, 0.3, 1] as const;
const HOST_EMAIL = "stefanromanpers@gmail.com";

interface ManageData {
  found: boolean;
  status?: string;
  start_utc?: string;
  visitor_timezone?: string;
  name?: string;
  can_cancel?: boolean;
  can_reschedule?: boolean;
  reschedule_count?: number;
  max_reschedules?: number;
}

export default function ManagePage({ params }: { params: Promise<{ token: string }> }) {
  const { token } = use(params);
  const [data, setData] = useState<ManageData | null>(null);
  const [mode, setMode] = useState<"view" | "reschedule">("view");
  const [confirmCancel, setConfirmCancel] = useState(false);
  const [cancelPhase, setCancelPhase] = useState<SubmitStatus | "idle">("idle");

  const load = useCallback(async () => {
    try {
      const res = await fetch(`/api/booking/manage/${token}`);
      setData((await res.json()) as ManageData);
    } catch {
      setData({ found: false });
    }
  }, [token]);

  useEffect(() => { void load(); }, [load]);

  async function doCancel() {
    setCancelPhase("loading");
    try {
      const res = await fetch(`/api/booking/manage/${token}/cancel`, { method: "POST" });
      const d = (await res.json()) as { success?: boolean };
      if (!res.ok || !d?.success) throw new Error("failed");
      setCancelPhase("success");
    } catch {
      setCancelPhase("error");
    }
  }

  const whenLabel =
    data?.start_utc
      ? new Intl.DateTimeFormat(undefined, {
          weekday: "long", day: "numeric", month: "long", hour: "2-digit", minute: "2-digit",
          timeZone: data.visitor_timezone || "Europe/Berlin",
        }).format(new Date(data.start_utc))
      : "";

  return (
    <main className="flex min-h-dvh items-center justify-center bg-black px-6 py-20">
      <div className="w-full max-w-md">
        <LazyMotion features={domAnimation}>
          <MotionConfig reducedMotion="user">
            {data === null ? (
              <p className="text-center text-sm text-text-tertiary">Loading…</p>
            ) : !data.found ? (
              <Card>
                <h1 className="font-display text-xl font-semibold text-text-primary">Link not found</h1>
                <p className="mt-2 text-sm text-text-secondary">
                  This management link is invalid or expired. Email{" "}
                  <a href={`mailto:${HOST_EMAIL}`} className="text-accent hover:underline">{HOST_EMAIL}</a>.
                </p>
              </Card>
            ) : data.status === "cancelled" ? (
              <Card>
                <h1 className="font-display text-xl font-semibold text-text-primary">Booking cancelled</h1>
                <p className="mt-2 text-sm text-text-secondary">This call has been cancelled.</p>
              </Card>
            ) : mode === "reschedule" ? (
              <BookingCalendar
                recipient={HOST_EMAIL}
                reschedule={{ token, onDone: () => { setMode("view"); void load(); } }}
              />
            ) : (
              <Card>
                <AnimatePresence mode="wait" initial={false}>
                  {cancelPhase !== "idle" ? (
                    <m.div key="cancel" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3, ease: EXPO }}>
                      <SubmitFeedback
                        status={cancelPhase}
                        loadingText="Cancelling…"
                        successText="Your call is cancelled."
                        errorText={<>Could not cancel. Email <a href={`mailto:${HOST_EMAIL}`} className="text-accent hover:underline">{HOST_EMAIL}</a>.</>}
                      />
                    </m.div>
                  ) : (
                    <m.div key="view" initial={{ opacity: 0 }} animate={{ opacity: 1 }} transition={{ duration: 0.3, ease: EXPO }}>
                      <h1 className="font-display text-xl font-semibold text-text-primary">Your call</h1>
                      <p className="mt-2 text-sm text-text-secondary">{whenLabel}</p>

                      <div className="mt-6 space-y-3">
                        {data.can_reschedule && (
                          <HeroButton type="button" variant="secondary" className="w-full" onClick={() => setMode("reschedule")}>
                            Reschedule
                          </HeroButton>
                        )}
                        {data.can_cancel && !confirmCancel && (
                          <button
                            type="button"
                            onClick={() => setConfirmCancel(true)}
                            className="w-full text-sm font-medium text-text-secondary underline-offset-4 outline-none transition-colors hover:text-red-400 focus-visible:underline"
                          >
                            Cancel this call
                          </button>
                        )}
                        {data.can_cancel && confirmCancel && (
                          <div className="rounded-[10px] border border-red-500/40 bg-red-500/5 p-4 text-center">
                            <p className="mb-3 text-sm text-text-secondary">Cancel this call? This cannot be undone.</p>
                            <div className="flex gap-2">
                              <button type="button" onClick={() => setConfirmCancel(false)} className="flex-1 rounded-[10px] border border-border py-2 text-sm text-text-secondary hover:border-accent/50">Keep it</button>
                              <button type="button" onClick={doCancel} className="flex-1 rounded-[10px] bg-red-500 py-2 text-sm font-medium text-white hover:bg-red-600">Yes, cancel</button>
                            </div>
                          </div>
                        )}
                        {!data.can_cancel && !data.can_reschedule && (
                          <p className="text-xs text-text-tertiary">
                            {(data.reschedule_count ?? 0) >= (data.max_reschedules ?? 2)
                              ? "You’ve rescheduled this call the maximum number of times. "
                              : "Changes close 24h before (cancel) and 12h before (reschedule). "}
                            To change it, email{" "}
                            <a href={`mailto:${HOST_EMAIL}`} className="text-accent hover:underline">{HOST_EMAIL}</a>.
                          </p>
                        )}
                      </div>
                    </m.div>
                  )}
                </AnimatePresence>
              </Card>
            )}
          </MotionConfig>
        </LazyMotion>
      </div>
    </main>
  );
}

function Card({ children }: { children: React.ReactNode }) {
  return <div className="rounded-2xl border border-border bg-surface/30 p-6 backdrop-blur-sm sm:p-8">{children}</div>;
}
```

- [ ] **Step 2: Typecheck + build** — from `frontend/`, `npx tsc --noEmit` (ignore transient `.next/` errors) then `npm run build` → `/manage/[token]` compiles.

---

## Task 9: Verification

- [ ] **Step 1: Backend** — `source venv/Scripts/activate && python -m pytest auth_service/tests/test_google_calendar.py auth_service/tests/test_booking_manage_email.py auth_service/tests/test_booking_manage_router.py auth_service/tests/test_booking_email.py auth_service/tests/test_booking_router.py auth_service/tests/test_booking_availability.py auth_service/tests/test_booking_reminder_email.py -v` → all pass.

- [ ] **Step 2: Frontend** — `npx tsc --noEmit` clean; `npm run build` succeeds.

- [ ] **Step 3: Manual smoke** (servers running, `BOOKING_PUBLIC_BASE_URL=http://localhost:3000` in `backend/.env`):
  - Make a booking → the client email contains a `/manage/{token}` link.
  - Open it → see the booking; Reschedule → pick a new time → calendar event moves + both emails; Cancel → event removed + both emails + slot freed.
  - Verify the reschedule button disappears after 2 reschedules and within 12h; cancel disappears within 24h.

---

## Operator note

Set `BOOKING_PUBLIC_BASE_URL` on **cms-backend-roman** (Vercel) to `https://roman-technologies.dev` (it's the default, so only needed if overriding) and to `http://localhost:3000` in local `backend/.env` for testing. Then restart the backend.

---

## Self-Review

**Spec coverage:** manage_token + google_event_id + reschedule_count (Task 1); config incl. max-reschedules + base URL (Task 2); delete/move event (Task 3); cancellation+reschedule emails both parties (Task 4); store token/event-id + manage link in client+reminder emails (Task 5); GET/cancel/reschedule endpoints with 24h/12h windows + 2-reschedule cap (Task 6); reschedule calendar mode (Task 7); manage page with view/cancel/reschedule + window/limit messaging (Task 8). ✅

**Placeholder scan:** none — every step has full code/SQL/commands.

**Type consistency:** `manage_token`/`google_event_id`/`reschedule_count` names match across migration, insert, queries, and endpoints; `booking_manage_email.send_cancellation`/`send_reschedule` signatures match the router calls; `google_calendar.delete_event`/`update_event_time` signatures match their tests and router calls; the frontend `reschedule={{ token, onDone }}` prop matches the `BookingCalendar` signature; `/api/booking/manage/{token}…` paths match the backend routes (mounted on the main app, same as the other booking routes). ✅
