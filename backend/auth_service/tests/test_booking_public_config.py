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
    business_name="Acme Corp",
    owner_notification_email="owner@acme.com",
    email_from_name="Acme",
    meeting_url="",
    slot_granularity_min=45,
    reminders_enabled=True,
    reminder_offsets_min=[60],
    calendar_provider="none",
    is_active=True,
    logo_url="https://acme.com/logo.png",
    primary_color="#123456",
    accent_color="#000000",
    widget_color="#abcdef",
)


@pytest.fixture
def client():
    return TestClient(app)


def test_public_config_returns_branding(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
    ):
        r = client.get("/booking/acme/config")
    assert r.status_code == 200
    body = r.json()
    assert body["public_slug"] == "acme"
    assert body["business_name"] == "Acme Corp"
    assert body["primary_color"] == "#123456"
    # Email accent and widget color are independent fields.
    assert body["accent_color"] == "#000000"
    assert body["widget_color"] == "#abcdef"
    assert body["logo_url"] == "https://acme.com/logo.png"
    assert body["locale"] == "en"


def test_public_config_unknown_slug_404(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=None
    ):
        r = client.get("/booking/unknown-slug/config")
    assert r.status_code == 404
