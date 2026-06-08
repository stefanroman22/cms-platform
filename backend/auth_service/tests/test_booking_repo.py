from datetime import datetime
from unittest.mock import MagicMock, patch
from zoneinfo import ZoneInfo

import pytest

from auth_service.services import booking_repo
from auth_service.services.booking_repo import BookingConflict

UTC = ZoneInfo("UTC")


def _sb():
    sb = MagicMock()
    for m in [
        "table",
        "select",
        "insert",
        "update",
        "upsert",
        "eq",
        "in_",
        "gte",
        "lte",
        "lt",
        "gt",
        "limit",
        "order",
    ]:
        getattr(sb, m).return_value = sb
    return sb


def _exec(sb, data):
    sb.execute.return_value = type("R", (), {"data": data})()
    return sb


def test_upsert_customer_returns_id():
    sb = _exec(_sb(), [{"id": "c1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        cid = booking_repo.upsert_customer(
            tenant_id="t1",
            name="Jane",
            email="j@a.com",
            phone=None,
            locale="en",
            timezone="Europe/London",
        )
    assert cid == "c1"


def test_insert_booking_translates_exclusion_violation():
    sb = _sb()
    sb.execute.side_effect = Exception("duplicate key value ... 23P01 conflicting")
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        with pytest.raises(BookingConflict):
            booking_repo.insert_booking(
                tenant_id="t1",
                service_id="s1",
                resource_id="r1",
                customer_id="c1",
                customer_name="Jane",
                start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
                end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
                guard_start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
                guard_end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
                manage_token_hash="h",
                source="widget",
                notes=None,
            )


def test_insert_booking_snapshots_customer_name():
    """A booking carries its own customer_name snapshot so a later booking from the
    same email (which overwrites the shared customer row) can't rewrite this one."""
    sb = _exec(_sb(), [{"id": "b1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        booking_repo.insert_booking(
            tenant_id="t1",
            service_id="s1",
            resource_id="r1",
            customer_id="c1",
            customer_name="Alice",
            start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
            end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
            guard_start_utc=datetime(2099, 1, 1, 9, 0, tzinfo=UTC),
            guard_end_utc=datetime(2099, 1, 1, 9, 45, tzinfo=UTC),
            manage_token_hash="h",
            source="widget",
            notes=None,
        )
    inserted = sb.insert.call_args[0][0]
    assert inserted["customer_name"] == "Alice"


def test_load_booking_by_token_hash_found():
    sb = _exec(_sb(), [{"id": "b1", "status": "confirmed"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        b = booking_repo.load_booking_by_token_hash("h")
    assert b["id"] == "b1"


def test_busy_by_resource_groups_guard_intervals():
    rows = [
        {
            "resource_id": "r1",
            "guard_start_utc": "2026-06-10T06:00:00+00:00",
            "guard_end_utc": "2026-06-10T06:45:00+00:00",
        },
        {
            "resource_id": "r1",
            "guard_start_utc": "2026-06-10T07:00:00+00:00",
            "guard_end_utc": "2026-06-10T07:45:00+00:00",
        },
        {
            "resource_id": "r2",
            "guard_start_utc": "2026-06-10T06:00:00+00:00",
            "guard_end_utc": "2026-06-10T06:45:00+00:00",
        },
    ]
    sb = _exec(_sb(), rows)
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        busy = booking_repo.busy_guard_intervals_by_resource(
            tenant_id="t1",
            resource_ids=["r1", "r2"],
            window_start_utc=datetime(2026, 6, 10, 0, 0, tzinfo=UTC),
            window_end_utc=datetime(2026, 6, 11, 0, 0, tzinfo=UTC),
        )
    assert len(busy["r1"]) == 2 and len(busy["r2"]) == 1
    assert busy["r1"][0][0] == datetime(2026, 6, 10, 6, 0, tzinfo=UTC)


# ---- P4 idempotency helpers ----


def test_notification_already_sent_true_when_row_exists():
    sb = _exec(_sb(), [{"id": "n1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        result = booking_repo.notification_already_sent("b1:reminder:60")
    assert result is True


def test_notification_already_sent_false_when_no_row():
    sb = _exec(_sb(), [])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        result = booking_repo.notification_already_sent("b1:reminder:60")
    assert result is False


def test_record_notification_inserts_row():
    sb = _exec(_sb(), [{"id": "n1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        booking_repo.record_notification(
            tenant_id="t1",
            booking_id="b1",
            type="reminder",
            offset_min=60,
            idempotency_key="b1:reminder:60",
        )
    # Assert table("booking_notifications_log").insert(...).execute() was called
    sb.table.assert_called_with("booking_notifications_log")
    sb.insert.assert_called_once()
    inserted = sb.insert.call_args[0][0]
    assert inserted["idempotency_key"] == "b1:reminder:60"
    assert inserted["offset_min"] == 60
    assert inserted["status"] == "sent"
    assert inserted["sent_at"] is not None


def test_record_notification_no_sent_at_when_error():
    sb = _exec(_sb(), [{"id": "n1"}])
    with patch("auth_service.services.booking_repo.get_supabase_admin", return_value=sb):
        booking_repo.record_notification(
            tenant_id="t1",
            booking_id="b1",
            type="reminder",
            offset_min=60,
            idempotency_key="b1:reminder:60",
            status="error",
            error="timeout",
        )
    inserted = sb.insert.call_args[0][0]
    assert inserted["status"] == "error"
    assert inserted["sent_at"] is None
