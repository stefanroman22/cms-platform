"""Booking availability speed changes (2026-06-21):

- GET /{slug}/availability carries an edge Cache-Control so Vercel's CDN can serve
  repeat reads (s-maxage) and revalidate in the background (stale-while-revalidate).
- That same route is intentionally NOT behind the per-IP _public_read_limit anymore
  (the edge cache absorbs repeats), while the sibling public reads (/config, ...) still
  are. Write paths keep their limiter and remain the double-booking boundary.
"""

from unittest.mock import patch

import pytest
from fastapi import HTTPException
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
    slot_granularity_min=30,
    reminders_enabled=False,
    reminder_offsets_min=[],
    calendar_provider="none",
    is_active=True,
)
SERVICE = {"id": "s1", "tenant_id": "t1", "name": "Cut", "duration_min": 30, "is_active": True}

CACHE_HEADER = "s-maxage=30, stale-while-revalidate=60"

AVAIL_PARAMS = {"service_id": "s1", "from": "2099-06-10", "to": "2099-06-17"}


@pytest.fixture
def client():
    return TestClient(app)


def test_availability_sets_edge_cache_control(client):
    """The availability read emits the edge Cache-Control so Vercel's CDN can absorb
    repeats (s-maxage) and revalidate in the background (stale-while-revalidate)."""
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug",
            return_value=TENANT,
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._availability_for_range", return_value=[]),
    ):
        r = client.get("/booking/acme/availability", params=AVAIL_PARAMS)
    assert r.status_code == 200, r.text
    assert r.headers.get("cache-control") == CACHE_HEADER


def test_availability_not_rate_limited_while_config_still_is(client):
    """Availability dropped the per-IP _public_read_limit (the edge cache absorbs repeats),
    so even when the limiter would 429, availability still serves. The sibling reads — here
    /config — keep the limiter and still 429. This pins the asymmetry."""
    boom = HTTPException(status_code=429, detail="rate limited")
    with (
        patch("auth_service.routers.booking.pg_rate_limit.enforce", side_effect=boom),
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug",
            return_value=TENANT,
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._availability_for_range", return_value=[]),
    ):
        avail = client.get("/booking/acme/availability", params=AVAIL_PARAMS)
        config = client.get("/booking/acme/config")
    assert avail.status_code == 200, avail.text
    assert config.status_code == 429, config.text
