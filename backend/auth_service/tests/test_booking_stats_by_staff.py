"""Task 4D — per-staff stats scope + by_staff aggregation.

Two coordinated changes are pinned here:
  1. GET /bookings/stats accepts an optional ``resource_id`` query param and threads
     it into the stats query (so KPIs/charts scope to a single staff member).
  2. The stats payload gains a ``by_staff`` array — one row per staff resource with
     a booking count and resolved name — built for the *unfiltered* call.

Pure aggregation (``compute_booking_stats``) and the router wiring are both tested.
"""

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut
from auth_service.services.booking_stats import compute_booking_stats

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}

NOW_UTC = datetime(2024, 3, 15, 10, 0, 0, tzinfo=UTC)
TZ = "Europe/Berlin"


@pytest.fixture
def client():
    return TestClient(app)


def _auth(user=OWNER, project=PROJECT):
    return (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=user),
        ),
        patch("auth_service.routers.booking_admin.require_project_access", return_value=project),
    )


def _row(status: str, start_utc: str, *, resource_id=None, resource_name=None) -> dict:
    return {
        "status": status,
        "start_utc": start_utc,
        "service_name": "Cut",
        "resource_id": resource_id,
        "resource_name": resource_name,
    }


# ── pure aggregation: by_staff ────────────────────────────────────────────────


def test_by_staff_groups_and_names():
    rows = [
        _row("confirmed", "2024-03-01T09:00:00+00:00", resource_id="rA", resource_name="Alice"),
        _row("confirmed", "2024-03-02T09:00:00+00:00", resource_id="rA", resource_name="Alice"),
        _row("completed", "2024-03-03T09:00:00+00:00", resource_id="rB", resource_name="Bob"),
    ]
    result = compute_booking_stats(rows, now_utc=NOW_UTC, tz_name=TZ)
    by_staff = {r["resource_id"]: r for r in result["by_staff"]}
    assert by_staff["rA"]["count"] == 2
    assert by_staff["rA"]["resource_name"] == "Alice"
    assert by_staff["rB"]["count"] == 1
    assert by_staff["rB"]["resource_name"] == "Bob"
    # most_common ordering: Alice (2) before Bob (1)
    assert result["by_staff"][0]["resource_id"] == "rA"


def test_by_staff_empty_for_no_bookings():
    result = compute_booking_stats([], now_utc=NOW_UTC, tz_name=TZ)
    assert result["by_staff"] == []


def test_by_staff_skips_rows_without_resource():
    rows = [
        _row("confirmed", "2024-03-01T09:00:00+00:00", resource_id=None, resource_name=None),
        _row("confirmed", "2024-03-02T09:00:00+00:00", resource_id="rA", resource_name="Alice"),
    ]
    result = compute_booking_stats(rows, now_utc=NOW_UTC, tz_name=TZ)
    assert [r["resource_id"] for r in result["by_staff"]] == ["rA"]


# ── router: resource_id filter threads into the repo query ────────────────────


def test_stats_passes_resource_id_to_repo(client):
    ru, rp = _auth()
    cfg = MagicMock()
    cfg.timezone = "UTC"
    rows = [_row("confirmed", "2024-03-15T12:00:00+00:00", resource_id="rA", resource_name="Alice")]
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id", return_value=cfg
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_bookings_for_stats",
            return_value=rows,
        ) as q,
    ):
        r = client.get("/projects/acme/bookings/stats?resource_id=rA")
    assert r.status_code == 200, r.text
    # resource_id forwarded to the repo as a keyword
    assert q.call_args.kwargs.get("resource_id") == "rA"
    body = r.json()
    assert body["kpis"]["total"] == 1
    assert "by_staff" in body


def test_stats_unfiltered_omits_resource_id(client):
    ru, rp = _auth()
    cfg = MagicMock()
    cfg.timezone = "UTC"
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id", return_value=cfg
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_bookings_for_stats",
            return_value=[],
        ) as q,
    ):
        r = client.get("/projects/acme/bookings/stats")
    assert r.status_code == 200, r.text
    assert q.call_args.kwargs.get("resource_id") is None
