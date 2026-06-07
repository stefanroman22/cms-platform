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
    def create_event(
        self,
        *,
        start_utc: datetime,
        end_utc: datetime,
        name: str,
        email: str,
        note: str,
        meeting_url: str,
    ) -> str | None: ...
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
            start_utc=start_utc,
            end_utc=end_utc,
            name=name,
            email=email,
            note=note,
            meeting_url=meeting_url,
        )

    def update_event(self, event_id, start_utc, end_utc) -> None:
        if google_calendar.is_configured():
            google_calendar.update_event_time(event_id, start_utc, end_utc)

    def delete_event(self, event_id) -> None:
        if google_calendar.is_configured():
            google_calendar.delete_event(event_id)


def provider_for(name: str) -> CalendarProvider:
    return GoogleCalendarProvider() if name == "google" else NoopCalendarProvider()
