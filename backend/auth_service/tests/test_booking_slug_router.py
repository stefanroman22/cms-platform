from datetime import datetime, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

UTC = ZoneInfo("UTC")


def _in_window_start() -> str:
    """An ISO start that satisfies SERVICE's lead_time_min/max_advance_days window."""
    return (datetime.now(UTC) + timedelta(days=2)).isoformat()


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
    is_active=True,
)
SERVICE = {
    "id": "s1",
    "tenant_id": "t1",
    "name": "Cut",
    "duration_min": 45,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "lead_time_min": 120,
    "max_advance_days": 120,
    "is_active": True,
    "sort_order": 0,
}
RESOURCE = {"id": "r1", "tenant_id": "t1", "name": "Chair 1", "is_active": True, "sort_order": 0}


@pytest.fixture
def client():
    return TestClient(app)


def test_unknown_slug_404(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=None
    ):
        r = client.get("/booking/nope/services")
    assert r.status_code == 404


def test_services_lists_active(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_active_services", return_value=[SERVICE]
        ),
    ):
        r = client.get("/booking/acme/services")
    assert r.status_code == 200
    assert r.json()["services"][0]["id"] == "s1"


def test_create_happy_path(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", return_value="b1"),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch("auth_service.routers.booking.booking_email.send_host_notification"),
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation"),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": _in_window_start(),
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
        )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["booking_id"] == "b1"
    assert "/manage/" in body["manage_url"]


def test_create_conflict_returns_409(client, monkeypatch):
    from auth_service.services.booking_repo import BookingConflict

    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[RESOURCE],
        ),
        patch("auth_service.routers.booking._free_resource_for", return_value="r1"),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch(
            "auth_service.routers.booking.booking_repo.insert_booking",
            side_effect=BookingConflict(),
        ),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": _in_window_start(),
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
        )
    assert r.status_code == 409


@pytest.mark.parametrize(
    "start_utc,label",
    [
        ((datetime.now(UTC) - timedelta(days=1)).isoformat(), "past"),
        ((datetime.now(UTC) + timedelta(days=200)).isoformat(), "beyond max_advance_days"),
        ((datetime.now(UTC) + timedelta(minutes=10)).isoformat(), "inside lead_time_min"),
    ],
)
def test_create_rejects_out_of_window_start(client, start_utc, label):
    """SEC-071: the create path re-validates the booking window server-side. Past,
    far-future (> max_advance_days) and lead-time-violating starts are rejected with a
    422 before any resource is held or booking row is written."""
    insert = patch("auth_service.routers.booking.booking_repo.insert_booking")
    free = patch("auth_service.routers.booking._free_resource_for", return_value="r1")
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        free as free_mock,
        insert as insert_mock,
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": start_utc,
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
        )
    assert r.status_code == 422, f"{label}: {r.text}"
    assert r.json()["detail"]["field"] == "start_utc"
    # Rejected before the resource was selected or the row written.
    free_mock.assert_not_called()
    insert_mock.assert_not_called()


def test_create_shared_rate_limit_returns_429(client):
    """SEC-057: the create write path is gated by the shared Postgres limiter
    (not only the per-process slowapi decorator) so the cap holds across Vercel
    serverless instances. When the shared limiter says "over", create returns 429
    before any tenant lookup, email send, or calendar write."""
    with patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": "2099-06-10T06:00:00+00:00",
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
        )
    assert r.status_code == 429, r.text


def test_manage_cancel_shared_rate_limit_returns_429(client):
    """SEC-057: the manage cancel write path is also gated by the shared limiter."""
    with patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False):
        r = client.post("/booking/manage/some-token/cancel")
    assert r.status_code == 429, r.text


def test_manage_reschedule_shared_rate_limit_returns_429(client):
    """SEC-057: the manage reschedule write path is also gated by the shared limiter."""
    with patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False):
        r = client.post(
            "/booking/manage/some-token/reschedule",
            json={"slot_start": "2099-06-10T06:00:00+00:00"},
        )
    assert r.status_code == 429, r.text


def test_tenant_isolation_route_scopes_to_resolved_tenant(client):
    """Isolation: the route only ever queries the tenant resolved from the slug.
    The client supplies no tenant id, so it cannot reach another tenant's data."""
    captured = {}

    def _capture(tenant_id):
        captured["tenant_id"] = tenant_id
        return []

    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_active_services", side_effect=_capture
        ),
    ):
        client.get("/booking/acme/services")
    # Always the resolved tenant ("t1") — never any value the caller could inject.
    assert captured["tenant_id"] == TENANT.tenant_id
