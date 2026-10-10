"""SEC-070 regression: the public ``GET /booking/{slug}/availability`` read must
carry the shared per-IP rate limit that every sibling public booking read has.

Availability was the only unauthenticated booking read deliberately left without
``Depends(_public_read_limit)``, relying solely on an edge ``Cache-Control`` header.
But Vercel's edge keys on the full request URL (path + query), so an attacker who
varies ``service_id``/``from``/``to``/``resource_id`` forces a guaranteed cache miss
and a fresh origin computation (~6 service-role DB queries + a day-by-day loop + an
outbound Google Calendar ``list_busy``) on every request — a per-IP DB + external
calendar amplification DoS against the one shared Supabase DB that serves all tenants.
"""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.services.booking_tenant import TenantConfig

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
    reminders_enabled=False,
    reminder_offsets_min=[],
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


def _tenant_and_service():
    return (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug",
            return_value=TENANT,
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_service",
            return_value=SERVICE,
        ),
    )


def test_slug_availability_rate_limited(client):
    """Slug /availability enforces the shared per-IP read limit (429 over cap),
    and short-circuits BEFORE any heavy per-range DB work."""
    t, s = _tenant_and_service()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=False),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources"
        ) as load_resources,
    ):
        r = client.get("/booking/acme/availability?service_id=s1&from=2026-01-01&to=2026-01-07")
    assert r.status_code == 429
    # The expensive availability computation must never run once the IP is over its cap.
    load_resources.assert_not_called()


def test_slug_availability_allows_normal_range(client):
    """A legitimate request under the cap still succeeds (limit is generous for real use)."""
    t, s = _tenant_and_service()
    with (
        t,
        s,
        patch("auth_service.routers.booking.pg_rate_limit.allow", return_value=True),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[],
        ),
    ):
        r = client.get("/booking/acme/availability?service_id=s1&from=2026-01-01&to=2026-01-07")
    assert r.status_code == 200
    assert r.json() == {"days": []}
