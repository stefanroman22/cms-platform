from datetime import datetime
from unittest.mock import patch
from zoneinfo import ZoneInfo

from auth_service.services import calendar_provider

UTC = ZoneInfo("UTC")


def test_provider_for_none_is_noop():
    p = calendar_provider.provider_for("none")
    assert (
        p.create_event(
            start_utc=datetime(2099, 1, 1, tzinfo=UTC),
            end_utc=datetime(2099, 1, 1, 1, tzinfo=UTC),
            name="x",
            email="x@x.com",
            note="",
            meeting_url="",
        )
        is None
    )
    assert p.list_busy(datetime(2099, 1, 1, tzinfo=UTC), datetime(2099, 1, 2, tzinfo=UTC)) == []


def test_provider_for_google_delegates_create():
    p = calendar_provider.provider_for("google")
    with (
        patch(
            "auth_service.services.calendar_provider.google_calendar.is_configured",
            return_value=True,
        ),
        patch(
            "auth_service.services.calendar_provider.google_calendar.create_event",
            return_value="evt123",
        ) as mk,
    ):
        evt = p.create_event(
            start_utc=datetime(2099, 1, 1, tzinfo=UTC),
            end_utc=datetime(2099, 1, 1, 1, tzinfo=UTC),
            name="Jane",
            email="j@a.com",
            note="hi",
            meeting_url="http://m",
        )
    assert evt == "evt123"
    mk.assert_called_once()
