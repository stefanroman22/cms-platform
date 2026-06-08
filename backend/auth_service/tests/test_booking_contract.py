"""Tests for the versioned create-booking contract: the public
`GET /booking/{slug}/contract` endpoint, field-level validation errors on
`POST /booking/{slug}`, and behavior preservation for already-valid payloads."""

from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.models.booking_contract import BOOKING_CONTRACT_VERSION
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


@pytest.fixture
def client():
    return TestClient(app)


# Distinct per-test forwarded IPs so the shared 5/hour create-booking limiter
# (keyed by client_ip) never collides with other booking test files when the
# whole suite runs together.
def _ip(n: int) -> dict[str, str]:
    return {"X-Forwarded-For": f"203.0.113.{n}"}


def test_contract_endpoint_returns_versioned_shape(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
    ):
        r = client.get("/booking/acme/contract")
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["version"] == BOOKING_CONTRACT_VERSION
    assert "service_id" in body["required"]
    assert "start_utc" in body["required"]
    assert "customer.name" in body["required"]
    assert "customer.email" in body["required"]
    fields = body["fields"]
    assert fields["service_id"]["type"] == "string"
    assert fields["start_utc"]["format"] == "date-time"
    assert fields["customer.email"]["format"] == "email"


def test_contract_endpoint_unknown_slug_404(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=None
    ):
        r = client.get("/booking/nope/contract")
    assert r.status_code == 404


def test_create_missing_email_names_the_field(client):
    """A miswired form omitting customer.email produces an actionable 422 that
    names the offending field — not a generic 'Invalid booking'."""
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": "2099-06-10T06:00:00+00:00",
                "customer": {"name": "Jane", "email": ""},
            },
            headers=_ip(1),
        )
    assert r.status_code == 422, r.text
    # Field identified somewhere in the error body.
    assert "customer.email" in r.text


def test_create_missing_name_names_the_field(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": "2099-06-10T06:00:00+00:00",
                "customer": {"name": "  ", "email": "jane@acme.com"},
            },
            headers=_ip(2),
        )
    assert r.status_code == 422, r.text
    assert "customer.name" in r.text


def test_create_bad_start_utc_names_the_field(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": "not-a-date",
                "customer": {"name": "Jane", "email": "jane@acme.com"},
            },
            headers=_ip(3),
        )
    assert r.status_code == 422, r.text
    assert "start_utc" in r.text


def test_create_valid_payload_still_succeeds(client, monkeypatch):
    """Behavior preserved: a complete, valid payload books exactly as before."""
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
            headers=_ip(4),
        )
    assert r.status_code == 200, r.text
    assert r.json()["booking_id"] == "b1"


def test_create_honeypot_still_silently_succeeds(client):
    """The honeypot path is unchanged: a filled `website` field returns success
    without booking, even though it would otherwise pass validation."""
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "start_utc": "2099-06-10T06:00:00+00:00",
                "customer": {"name": "Bot", "email": "bot@x.com"},
                "website": "spam",
            },
            headers=_ip(5),
        )
    assert r.status_code == 200
    assert r.json()["success"] is True
