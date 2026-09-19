"""SEC-058 regression: the legacy unauthenticated booking read endpoints
(`GET /booking/availability`, `GET /booking/slots`) must carry the shared
per-IP rate limit that every other public booking read has, and the legacy
`/availability` range must be bounded so a single request cannot force an
unbounded day-by-day computation loop (CPU DoS).
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

TENANT = TenantConfig(
    tenant_id="t1",
    public_slug="roman-technologies-website",
    timezone="Europe/Bucharest",
    locale="en",
    business_name="Roman",
    owner_notification_email="owner@roman.com",
    email_from_name="Roman",
    meeting_url="",
    slot_granularity_min=45,
    reminders_enabled=False,
    reminder_offsets_min=[],
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
    "max_advance_days": 60,
    "is_active": True,
    "sort_order": 0,
}


@pytest.fixture
def client():
    return TestClient(app)


def _tenant_and_services():
    return (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug",
            return_value=TENANT,
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_active_services",
            return_value=[SERVICE],
        ),
    )


def test_legacy_availability_rate_limited(client):
    """Legacy /availability enforces the shared per-IP read limit (429 over cap)."""
    t, s = _tenant_and_services()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False),
    ):
        r = client.get("/booking/availability?from=2026-01-01&to=2026-01-07")
    assert r.status_code == 429


def test_legacy_slots_rate_limited(client):
    """Legacy /slots enforces the shared per-IP read limit (429 over cap)."""
    t, s = _tenant_and_services()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False),
    ):
        r = client.get("/booking/slots?date=2026-01-01")
    assert r.status_code == 429


def test_legacy_availability_rejects_unbounded_range(client):
    """A multi-millennium span is rejected (422) BEFORE any per-day computation,
    so it cannot be used as a single-request CPU-amplification DoS."""
    t, s = _tenant_and_services()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=True),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources"
        ) as load_resources,
    ):
        r = client.get("/booking/availability?from=2000-01-01&to=3000-01-01")
    assert r.status_code == 422
    # The heavy per-range DB load must never be reached for an abusive span.
    load_resources.assert_not_called()


def test_legacy_availability_allows_normal_range(client):
    """A legitimate small range still succeeds (the clamp is lossless for real use)."""
    t, s = _tenant_and_services()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=True),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[],
        ),
    ):
        r = client.get("/booking/availability?from=2026-01-01&to=2026-01-07")
    assert r.status_code == 200
    assert r.json() == {"days": []}
