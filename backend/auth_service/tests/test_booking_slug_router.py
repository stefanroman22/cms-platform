from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
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
                "start_utc": "2099-06-10T06:00:00+00:00",
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
                "start_utc": "2099-06-10T06:00:00+00:00",
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
        )
    assert r.status_code == 409


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
