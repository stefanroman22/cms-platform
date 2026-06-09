"""Tier A — per-barber public flow: select service -> select barber -> per-barber
time. Pins the new public surface:
  - GET /booking/{slug}/resources (eligible-for-service, or all active staff)
  - GET /booking/{slug}/availability?...&resource_id=  scopes slots to one barber
  - POST /booking/{slug} honors body.resource_id (and 409s if that barber is taken)
  - _free_resource_for(prefer_resource_id=...) returns the requested barber if free,
    else None (eligible-but-busy or not-eligible both yield None)
"""

from datetime import UTC, date, datetime, time, timedelta
from unittest.mock import patch
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from auth_service.core.config import settings
from auth_service.main import app
from auth_service.routers import booking as booking_router
from auth_service.services.booking_tenant import TenantConfig

TZ = "Europe/Bucharest"
UTC_TZ = ZoneInfo("UTC")

TENANT = TenantConfig(
    tenant_id="t1",
    public_slug="acme",
    timezone=TZ,
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
SERVICE = {
    "id": "s1",
    "tenant_id": "t1",
    "name": "Cut",
    "duration_min": 30,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "lead_time_min": 0,
    "max_advance_days": 365,
    "is_active": True,
    "sort_order": 0,
}
STAFF_A = {"id": "staff-A", "tenant_id": "t1", "name": "Alice", "type": "staff", "is_active": True}
STAFF_B = {"id": "staff-B", "tenant_id": "t1", "name": "Bob", "type": "staff", "is_active": True}

DAY = datetime(2099, 6, 10).date()  # Wednesday, dow=3
HOURS = [
    {"resource_id": "staff-A", "weekday": 3, "start_time": "09:00", "end_time": "17:00"},
    {"resource_id": "staff-B", "weekday": 3, "start_time": "09:00", "end_time": "17:00"},
]


@pytest.fixture
def client():
    return TestClient(app)


def _ip(n: int) -> dict[str, str]:
    return {"X-Forwarded-For": f"198.51.100.{n}"}


# ---------- GET /{slug}/resources ----------


def test_resources_endpoint_lists_eligible_for_service(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[STAFF_A, STAFF_B],
        ),
    ):
        r = client.get("/booking/acme/resources", params={"service_id": "s1"})
    assert r.status_code == 200, r.text
    resources = r.json()["resources"]
    assert [x["id"] for x in resources] == ["staff-A", "staff-B"]
    assert resources[0]["name"] == "Alice"
    assert resources[0]["type"] == "staff"


def test_resources_endpoint_lists_all_active_without_service(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch(
            "auth_service.routers.booking.booking_repo.load_active_resources",
            return_value=[STAFF_A],
        ),
    ):
        r = client.get("/booking/acme/resources")
    assert r.status_code == 200, r.text
    assert [x["id"] for x in r.json()["resources"]] == ["staff-A"]


def test_resources_unknown_slug_404(client):
    with patch(
        "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=None
    ):
        r = client.get("/booking/nope/resources")
    assert r.status_code == 404


# ---------- GET /{slug}/availability?resource_id= ----------


def test_availability_resource_filter_scopes_to_one_barber(client):
    """With resource_id, the busy query (and thus the slots) is scoped to that one
    barber even though two are eligible for the service. Uses a near-future date so
    the route's real `now` keeps it inside the service booking window."""
    target = date.today() + timedelta(days=3)
    dow = target.isoweekday() % 7  # Postgres dow (0=Sun)
    hours = [
        {"resource_id": "staff-A", "weekday": dow, "start_time": "09:00", "end_time": "17:00"},
        {"resource_id": "staff-B", "weekday": dow, "start_time": "09:00", "end_time": "17:00"},
    ]
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[STAFF_A, STAFF_B],
        ),
        patch("auth_service.routers.booking.booking_repo.load_hours", return_value=hours),
        patch("auth_service.routers.booking.booking_repo.load_exceptions", return_value=[]),
        patch(
            "auth_service.routers.booking.booking_repo.busy_guard_intervals_by_resource",
            return_value={},
        ) as busy,
    ):
        r = client.get(
            "/booking/acme/availability",
            params={
                "service_id": "s1",
                "from": target.isoformat(),
                "to": target.isoformat(),
                "resource_id": "staff-A",
            },
        )
    assert r.status_code == 200, r.text
    busy.assert_called_once()
    assert busy.call_args.kwargs["resource_ids"] == ["staff-A"]
    assert r.json()["days"], "expected slots for the selected barber"


def test_availability_resource_not_eligible_yields_no_days(client):
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch(
            "auth_service.routers.booking.booking_repo.load_eligible_resources",
            return_value=[STAFF_A],
        ),
    ):
        r = client.get(
            "/booking/acme/availability",
            params={
                "service_id": "s1",
                "from": "2099-06-10",
                "to": "2099-06-10",
                "resource_id": "staff-B",
            },
        )
    assert r.status_code == 200, r.text
    assert r.json()["days"] == []


# ---------- _free_resource_for(prefer_resource_id=...) ----------


def _free_ctx(busy=None):
    return (
        patch.object(
            booking_router.booking_repo,
            "load_eligible_resources",
            return_value=[STAFF_A, STAFF_B],
        ),
        patch.object(booking_router.booking_repo, "load_hours", return_value=HOURS),
        patch.object(booking_router.booking_repo, "load_exceptions", return_value=[]),
        patch.object(
            booking_router.booking_repo,
            "busy_guard_intervals_by_resource",
            return_value=busy or {},
        ),
    )


def test_prefer_resource_returns_it_when_free():
    start = datetime.combine(DAY, time(10, 0), tzinfo=ZoneInfo(TZ)).astimezone(UTC)
    now = datetime(2099, 6, 1, tzinfo=UTC)
    ctxs = _free_ctx()
    with ctxs[0], ctxs[1], ctxs[2], ctxs[3]:
        rid = booking_router._free_resource_for(
            cfg=TENANT, service=SERVICE, start_utc=start, now_utc=now, prefer_resource_id="staff-B"
        )
    assert rid == "staff-B"


def test_prefer_resource_busy_returns_none():
    start = datetime.combine(DAY, time(10, 0), tzinfo=ZoneInfo(TZ)).astimezone(UTC)
    now = datetime(2099, 6, 1, tzinfo=UTC)
    # staff-B is busy across the requested start; staff-A is free but not preferred.
    busy = {"staff-B": [(start, start + booking_router.timedelta(minutes=30))]}
    ctxs = _free_ctx(busy=busy)
    with ctxs[0], ctxs[1], ctxs[2], ctxs[3]:
        rid = booking_router._free_resource_for(
            cfg=TENANT, service=SERVICE, start_utc=start, now_utc=now, prefer_resource_id="staff-B"
        )
    assert rid is None


def test_prefer_resource_not_eligible_returns_none():
    start = datetime.combine(DAY, time(10, 0), tzinfo=ZoneInfo(TZ)).astimezone(UTC)
    now = datetime(2099, 6, 1, tzinfo=UTC)
    with patch.object(
        booking_router.booking_repo, "load_eligible_resources", return_value=[STAFF_A]
    ):
        rid = booking_router._free_resource_for(
            cfg=TENANT, service=SERVICE, start_utc=start, now_utc=now, prefer_resource_id="staff-B"
        )
    assert rid is None


# ---------- POST /{slug} honors resource_id ----------


def test_create_honors_resource_id(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    captured = {}

    def _fake_insert(**kwargs):
        captured["resource_id"] = kwargs["resource_id"]
        return "b1"

    def _fake_free(
        *, cfg, service, start_utc, now_utc, exclude_booking_id=None, prefer_resource_id=None
    ):
        captured["prefer"] = prefer_resource_id
        return prefer_resource_id or "auto"

    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._free_resource_for", _fake_free),
        patch("auth_service.routers.booking.booking_repo.upsert_customer", return_value="c1"),
        patch("auth_service.routers.booking.booking_repo.insert_booking", _fake_insert),
        patch("auth_service.routers.booking.booking_repo.update_booking"),
        patch("auth_service.routers.booking.booking_repo.insert_audit"),
        patch("auth_service.routers.booking.booking_email.send_host_notification"),
        patch("auth_service.routers.booking.booking_email.send_visitor_confirmation"),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "resource_id": "staff-B",
                "start_utc": "2099-06-10T08:00:00+00:00",
                "customer": {"name": "Jane", "email": "jane@acme.com", "tz": "Europe/London"},
            },
            headers=_ip(10),
        )
    assert r.status_code == 200, r.text
    assert captured["prefer"] == "staff-B"
    assert captured["resource_id"] == "staff-B"


def test_create_resource_taken_returns_409(client, monkeypatch):
    monkeypatch.setattr(settings, "RESEND_API_KEY", "k")
    with (
        patch(
            "auth_service.routers.booking.booking_tenant.load_tenant_by_slug", return_value=TENANT
        ),
        patch("auth_service.routers.booking.booking_repo.load_service", return_value=SERVICE),
        patch("auth_service.routers.booking._free_resource_for", return_value=None),
    ):
        r = client.post(
            "/booking/acme",
            json={
                "service_id": "s1",
                "resource_id": "staff-B",
                "start_utc": "2099-06-10T08:00:00+00:00",
                "customer": {"name": "Jane", "email": "jane@acme.com"},
            },
            headers=_ip(11),
        )
    assert r.status_code == 409
