from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC = ZoneInfo("UTC")
TENANT = TenantConfig(
    tenant_id="t1",
    public_slug="acme",
    timezone="Europe/Bucharest",
    locale="en",
    business_name="Acme",
    owner_notification_email="owner@acme.com",
    email_from_name="Acme",
    meeting_url="",
    slot_granularity_min=45,
    reminders_enabled=True,
    reminder_offsets_min=[60],
    calendar_provider="none",
    is_active=True,
)
POLICY = {
    "allow_cancel": True,
    "cancellation_window_hours": 24,
    "allow_reschedule": True,
    "reschedule_window_hours": 12,
    "max_reschedules": 2,
}


@pytest.fixture
def client():
    return TestClient(app)


def _booking(**over):
    b = {
        "id": "b1",
        "tenant_id": "t1",
        "service_id": "s1",
        "customer_id": "c1",
        "status": "confirmed",
        "start_utc": "2099-06-10T06:00:00+00:00",
        "end_utc": "2099-06-10T06:45:00+00:00",
        "reschedule_count": 0,
        "google_event_id": None,
    }
    b.update(over)
    return b


def test_manage_get_not_found(client):
    with patch(
        "auth_service.routers.booking.booking_repo.load_booking_by_token_hash", return_value=None
    ):
        r = client.get("/booking/manage/abc")
    assert r.status_code == 200 and r.json()["found"] is False


def test_manage_get_flags(client):
    with (
        patch(
            "auth_service.routers.booking.booking_repo.load_booking_by_token_hash",
            return_value=_booking(),
        ),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"name": "Jane", "email": "j@a.com", "timezone": "Europe/London"},
        ),
    ):
        r = client.get("/booking/manage/abc")
    body = r.json()
    assert body["found"] is True and body["can_cancel"] is True
    assert body["public_slug"] == "acme"
    assert body["service_id"] == "s1"


def test_cancel_too_late_rejected(client):
    from datetime import datetime, timedelta

    soon = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    with (
        patch(
            "auth_service.routers.booking.booking_repo.load_booking_by_token_hash",
            return_value=_booking(start_utc=soon),
        ),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
    ):
        r = client.post("/booking/manage/abc/cancel")
    assert r.status_code == 403


def test_cancel_success(client):
    with (
        patch(
            "auth_service.routers.booking.booking_repo.load_booking_by_token_hash",
            return_value=_booking(),
        ),
        patch("auth_service.routers.booking.booking_tenant.load_tenant_by_id", return_value=TENANT),
        patch("auth_service.routers.booking.booking_repo.load_policy", return_value=POLICY),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch(
            "auth_service.routers.booking.booking_repo.load_customer",
            return_value={"name": "Jane", "email": "j@a.com", "timezone": "Europe/London"},
        ),
        patch("auth_service.routers.booking.booking_manage_email.send_cancellation"),
    ):
        r = client.post("/booking/manage/abc/cancel")
    assert r.status_code == 200 and r.json()["success"] is True
