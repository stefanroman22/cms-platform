from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from auth_service.core.config import settings
from auth_service.services import google_calendar

UTC = ZoneInfo("UTC")


def test_is_configured(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "")
    assert google_calendar.is_configured() is False
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_ID", "x")
    monkeypatch.setattr(settings, "GOOGLE_CLIENT_SECRET", "y")
    monkeypatch.setattr(settings, "GOOGLE_REFRESH_TOKEN", "z")
    assert google_calendar.is_configured() is True


def test_busy_intervals_filters_allday_free_declined():
    payload = {
        "items": [
            {
                "start": {"dateTime": "2026-06-10T10:00:00+00:00"},
                "end": {"dateTime": "2026-06-10T11:00:00+00:00"},
            },
            {
                "start": {"date": "2026-06-10"},
                "end": {"date": "2026-06-11"},
            },  # all-day birthday/holiday
            {
                "start": {"dateTime": "2026-06-10T12:00:00+00:00"},
                "end": {"dateTime": "2026-06-10T13:00:00+00:00"},
                "transparency": "transparent",
            },
            {
                "start": {"dateTime": "2026-06-10T14:00:00+00:00"},
                "end": {"dateTime": "2026-06-10T15:00:00+00:00"},
                "attendees": [{"self": True, "responseStatus": "declined"}],
            },
        ]
    }
    with patch("auth_service.services.google_calendar._api", return_value=payload):
        out = google_calendar.busy_intervals(
            datetime(2026, 6, 10, tzinfo=UTC), datetime(2026, 6, 11, tzinfo=UTC)
        )
    assert out == [
        (datetime(2026, 6, 10, 10, 0, tzinfo=UTC), datetime(2026, 6, 10, 11, 0, tzinfo=UTC))
    ]


def test_create_event_posts_and_returns_id():
    captured = {}

    def fake_api(method, path, *, params=None, body=None):
        captured.update(method=method, path=path, params=params, body=body)
        return {"id": "evt1"}

    with patch("auth_service.services.google_calendar._api", side_effect=fake_api):
        eid = google_calendar.create_event(
            start_utc=datetime(2026, 6, 10, 6, 0, tzinfo=UTC),
            end_utc=datetime(2026, 6, 10, 6, 45, tzinfo=UTC),
            name="Jane",
            email="jane@acme.com",
            note="hi",
            meeting_url="https://meet.example/abc",
        )
    assert eid == "evt1"
    assert captured["method"] == "POST"
    assert captured["body"]["summary"] == "Call with Jane"  # host event = client name
    assert "attendees" not in captured["body"]  # client NOT invited → not auto-added
    assert "jane@acme.com" in captured["body"]["description"]  # contact in description
    assert captured["body"]["location"] == "https://meet.example/abc"
    assert captured["params"]["sendUpdates"] == "none"


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
