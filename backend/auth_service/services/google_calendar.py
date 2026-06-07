"""Minimal Google Calendar client over urllib — no extra dependencies, mirrors
the Resend-over-urllib pattern. Reads busy intervals (to keep availability in
sync with the host's real calendar) and creates the booking event on the host
calendar.

When GOOGLE_* settings are empty `is_configured()` is False and callers fall
back to Supabase-only availability (no calendar read/write). Both `start_utc`
and `end_utc` passed to busy_intervals must be tz-aware UTC; busy_intervals
returns tz-aware UTC datetimes."""

from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from zoneinfo import ZoneInfo

from ..core.config import settings

log = logging.getLogger(__name__)
_UTC = ZoneInfo("UTC")
_token_cache: dict[str, object] = {"value": "", "exp": 0.0}


def is_configured() -> bool:
    return bool(
        settings.GOOGLE_CLIENT_ID
        and settings.GOOGLE_CLIENT_SECRET
        and settings.GOOGLE_REFRESH_TOKEN
    )


def _access_token() -> str:
    now = time.time()
    cached = _token_cache.get("value")
    if cached and float(_token_cache.get("exp", 0.0)) - 60 > now:
        return str(cached)
    data = urllib.parse.urlencode(
        {
            "client_id": settings.GOOGLE_CLIENT_ID,
            "client_secret": settings.GOOGLE_CLIENT_SECRET,
            "refresh_token": settings.GOOGLE_REFRESH_TOKEN,
            "grant_type": "refresh_token",
        }
    ).encode()
    req = urllib.request.Request("https://oauth2.googleapis.com/token", data=data, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            payload = json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google token refresh {e.code}: {e.read().decode()}") from e
    _token_cache["value"] = payload["access_token"]
    _token_cache["exp"] = now + float(payload.get("expires_in", 3600))
    return str(_token_cache["value"])


def _api(method: str, path: str, *, params: dict | None = None, body: dict | None = None) -> dict:
    url = "https://www.googleapis.com/calendar/v3" + path
    if params:
        url += "?" + urllib.parse.urlencode(params)
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Authorization": f"Bearer {_access_token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"Google Calendar {e.code}: {e.read().decode()}") from e


def busy_intervals(start_utc: datetime, end_utc: datetime) -> list[tuple[datetime, datetime]]:
    """Busy windows on the host calendar in [start, end]. Only TIMED, opaque
    (busy), non-declined events count — all-day events (birthdays, public
    holidays) and 'Free'/declined events are ignored, so clients can still book
    on those days."""
    cal = urllib.parse.quote(settings.GOOGLE_CALENDAR_ID, safe="")
    payload = _api(
        "GET",
        f"/calendars/{cal}/events",
        params={
            "timeMin": start_utc.isoformat(),
            "timeMax": end_utc.isoformat(),
            "singleEvents": "true",
            "orderBy": "startTime",
            "maxResults": "2500",
        },
    )
    out: list[tuple[datetime, datetime]] = []
    for ev in payload.get("items", []):
        start = ev.get("start", {})
        end = ev.get("end", {})
        if "dateTime" not in start or "dateTime" not in end:
            continue  # all-day → never blocks
        if ev.get("transparency") == "transparent":
            continue  # marked Free
        if any(
            a.get("self") and a.get("responseStatus") == "declined" for a in ev.get("attendees", [])
        ):
            continue  # host declined
        out.append(
            (
                datetime.fromisoformat(start["dateTime"]).astimezone(_UTC),
                datetime.fromisoformat(end["dateTime"]).astimezone(_UTC),
            )
        )
    return out


def create_event(
    *, start_utc: datetime, end_utc: datetime, name: str, email: str, note: str, meeting_url: str
) -> str | None:
    """Create the booking on the HOST calendar only. The client is NOT added as
    an attendee, so the event does not auto-appear on their calendar — they
    self-add via the 'Add to Google Calendar' button in their email. The client
    contact lives in the description. Returns the created event id."""
    cal = urllib.parse.quote(settings.GOOGLE_CALENDAR_ID, safe="")
    desc = f"Booked via roman-technologies.dev\n\nWith: {name} ({email})"
    if note:
        desc += f"\n\nNote: {note}"
    if meeting_url:
        desc += f"\n\nJoin: {meeting_url}"
    body: dict = {
        "summary": f"Call with {name}",
        "description": desc,
        "start": {"dateTime": start_utc.isoformat()},
        "end": {"dateTime": end_utc.isoformat()},
    }
    if meeting_url:
        body["location"] = meeting_url
    payload = _api("POST", f"/calendars/{cal}/events", params={"sendUpdates": "none"}, body=body)
    return payload.get("id")


def delete_event(event_id: str) -> None:
    """Remove the host-calendar event. A 404/410 (already gone) is ignored."""
    cal = urllib.parse.quote(settings.GOOGLE_CALENDAR_ID, safe="")
    eid = urllib.parse.quote(event_id, safe="")
    try:
        _api("DELETE", f"/calendars/{cal}/events/{eid}", params={"sendUpdates": "none"})
    except RuntimeError as exc:
        # Match the "Google Calendar <code>:" prefix (not body text) so only a
        # genuine 404/410 (event already gone) is swallowed.
        if str(exc).startswith("Google Calendar 404:") or str(exc).startswith(
            "Google Calendar 410:"
        ):
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
        body={
            "start": {"dateTime": start_utc.isoformat()},
            "end": {"dateTime": end_utc.isoformat()},
        },
    )
