"""Tests for appointment management endpoints (Phase 2b).

Patches require_user / require_project_access at
auth_service.routers.booking_admin.* (same pattern as test_booking_admin_router.py).
Repo / availability functions are patched at their call sites in the router module.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}

_SERVICE = {
    "id": "svc1",
    "name": "Haircut",
    "duration_min": 30,
    "buffer_before_min": 0,
    "buffer_after_min": 0,
    "lead_time_min": 60,
    "max_advance_days": 60,
    "is_active": True,
}

_TENANT_CFG_ROW = {
    "tenant_id": "t1",
    "public_slug": "acme",
    "timezone": "UTC",
    "locale": "en",
    "business_name": "Acme",
    "owner_notification_email": "o@acme.com",
    "email_from_name": "Acme",
    "meeting_url": "",
    "slot_granularity_min": 15,
    "reminders_enabled": False,
    "reminder_offsets_min": [],
    "calendar_provider": "none",
    "is_active": True,
}


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


# ---------------------------------------------------------------------------
# GET /appointments — list
# ---------------------------------------------------------------------------


def _raw_appointment(**overrides):
    base = {
        "id": "bk1",
        "status": "confirmed",
        "start_utc": "2026-07-01T10:00:00+00:00",
        "end_utc": "2026-07-01T10:30:00+00:00",
        "reschedule_count": 0,
        "notes": None,
        "source": "widget",
        "service_id": "svc1",
        "resource_id": "res1",
        "customer_id": "cust1",
        "booking_customers": {
            "name": "Alice",
            "email": "alice@example.com",
            "phone": None,
            "timezone": "UTC",
        },
        "booking_services": {"name": "Haircut"},
        "booking_resources": {"name": "Staff"},
    }
    base.update(overrides)
    return base


def test_list_appointments_returns_flattened_rows(client):
    ru, rp = _auth()
    rows = [_raw_appointment()]
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_appointments",
            return_value=rows,
        ),
    ):
        r = client.get("/projects/acme/bookings/appointments")
    assert r.status_code == 200
    appts = r.json()["appointments"]
    assert len(appts) == 1
    a = appts[0]
    assert a["customer_name"] == "Alice"
    assert a["customer_email"] == "alice@example.com"
    assert a["service_name"] == "Haircut"
    assert a["resource_name"] == "Staff"
    # Original embedded keys should not appear at top level
    assert "booking_customers" not in a
    assert "booking_services" not in a
    assert "booking_resources" not in a


def test_list_appointments_ownership_403(client):
    with (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=OWNER),
        ),
        patch(
            "auth_service.routers.booking_admin.require_project_access",
            side_effect=HTTPException(status_code=403, detail="Access denied"),
        ),
    ):
        r = client.get("/projects/someone-else/bookings/appointments")
    assert r.status_code == 403


# ---------------------------------------------------------------------------
# POST /appointments — manual create
# ---------------------------------------------------------------------------

_CREATE_BODY = {
    "service_id": "svc1",
    "start_utc": "2026-07-01T10:00:00+00:00",
    "customer": {"name": "Bob", "email": "bob@example.com"},
}


def _mock_tenant_config():
    from auth_service.services.booking_tenant import TenantConfig

    return TenantConfig(
        tenant_id="t1",
        public_slug="acme",
        timezone="UTC",
        locale="en",
        business_name="Acme",
        owner_notification_email="o@acme.com",
        email_from_name="Acme",
        meeting_url="",
        slot_granularity_min=15,
        reminders_enabled=False,
        reminder_offsets_min=[],
        calendar_provider="none",
        is_active=True,
    )


def test_create_appointment_assigns_resource_and_returns_201(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value="res1"),
        patch(
            "auth_service.routers.booking_admin.booking_repo.upsert_customer", return_value="cust1"
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_booking", return_value="bk2"),
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.post("/projects/acme/bookings/appointments", json=_CREATE_BODY)
    assert r.status_code == 201
    body = r.json()
    assert body["booking_id"] == "bk2"


def test_create_appointment_no_free_resource_409(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value=None),
    ):
        r = client.post("/projects/acme/bookings/appointments", json=_CREATE_BODY)
    assert r.status_code == 409


def test_create_appointment_booking_conflict_409(client):
    from auth_service.services.booking_repo import BookingConflict

    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value="res1"),
        patch(
            "auth_service.routers.booking_admin.booking_repo.upsert_customer", return_value="cust1"
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.insert_booking",
            side_effect=BookingConflict(),
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.post("/projects/acme/bookings/appointments", json=_CREATE_BODY)
    assert r.status_code == 409


def test_create_appointment_with_explicit_resource_id(client):
    """When resource_id is provided, _free_resource_for is NOT called."""
    ru, rp = _auth()
    body = {**_CREATE_BODY, "resource_id": "res-explicit"}
    free_mock = patch("auth_service.routers.booking_admin._free_resource_for")
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        free_mock as fm,
        patch(
            "auth_service.routers.booking_admin.booking_repo.upsert_customer", return_value="cust1"
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_booking", return_value="bk3"),
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.post("/projects/acme/bookings/appointments", json=body)
    assert r.status_code == 201
    fm.assert_not_called()


# ---------------------------------------------------------------------------
# PATCH /appointments/{id} — actions
# ---------------------------------------------------------------------------

_BOOKING_ROW = {
    "id": "bk1",
    "tenant_id": "t1",
    "service_id": "svc1",
    "resource_id": "res1",
    "customer_id": "cust1",
    "status": "confirmed",
    "start_utc": "2026-07-01T10:00:00+00:00",
    "end_utc": "2026-07-01T10:30:00+00:00",
    "guard_start_utc": "2026-07-01T10:00:00+00:00",
    "guard_end_utc": "2026-07-01T10:30:00+00:00",
    "reschedule_count": 0,
}


def test_patch_unknown_booking_404(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking", return_value=None
        ),
    ):
        r = client.patch("/projects/acme/bookings/appointments/nope", json={"action": "cancel"})
    assert r.status_code == 404


def test_patch_cancel_sets_status(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch("auth_service.routers.booking_admin.booking_repo.update_booking") as upd,
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
        patch("auth_service.routers.booking_admin._notify_client_cancelled") as notify,
    ):
        r = client.patch(
            "/projects/acme/bookings/appointments/bk1",
            json={"action": "cancel", "reason": "owner cancelled"},
        )
    assert r.status_code == 200
    call_fields = upd.call_args[0][1]
    assert call_fields["status"] == "cancelled"
    assert "cancel_reason" in call_fields
    notify.assert_called_once()  # client is emailed about the cancellation


def test_patch_no_show_sets_status(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch("auth_service.routers.booking_admin.booking_repo.update_booking") as upd,
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.patch("/projects/acme/bookings/appointments/bk1", json={"action": "no_show"})
    assert r.status_code == 200
    assert upd.call_args[0][1]["status"] == "no_show"


def test_patch_complete_sets_status(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch("auth_service.routers.booking_admin.booking_repo.update_booking") as upd,
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.patch("/projects/acme/bookings/appointments/bk1", json={"action": "complete"})
    assert r.status_code == 200
    assert upd.call_args[0][1]["status"] == "completed"


def test_patch_reschedule_success(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value="res1"),
        patch("auth_service.routers.booking_admin.booking_repo.update_booking") as upd,
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
        patch("auth_service.routers.booking_admin._notify_client_rescheduled") as notify,
    ):
        r = client.patch(
            "/projects/acme/bookings/appointments/bk1",
            json={"action": "reschedule", "start_utc": "2026-07-02T10:00:00+00:00"},
        )
    assert r.status_code == 200
    call_fields = upd.call_args[0][1]
    assert "start_utc" in call_fields
    assert "end_utc" in call_fields
    assert call_fields["resource_id"] == "res1"
    notify.assert_called_once()  # client is emailed about the reschedule


def test_patch_reschedule_conflict_409(client):
    from auth_service.services.booking_repo import BookingConflict

    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value="res1"),
        patch(
            "auth_service.routers.booking_admin.booking_repo.update_booking",
            side_effect=BookingConflict(),
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.patch(
            "/projects/acme/bookings/appointments/bk1",
            json={"action": "reschedule", "start_utc": "2026-07-02T10:00:00+00:00"},
        )
    assert r.status_code == 409


def test_patch_reschedule_no_free_resource_409(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_booking",
            return_value=_BOOKING_ROW,
        ),
        patch(
            "auth_service.routers.booking_admin.booking_repo.load_service", return_value=_SERVICE
        ),
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id",
            return_value=_mock_tenant_config(),
        ),
        patch("auth_service.routers.booking_admin._free_resource_for", return_value=None),
    ):
        r = client.patch(
            "/projects/acme/bookings/appointments/bk1",
            json={"action": "reschedule", "start_utc": "2026-07-02T10:00:00+00:00"},
        )
    assert r.status_code == 409


def test_patch_ownership_403(client):
    with (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=OWNER),
        ),
        patch(
            "auth_service.routers.booking_admin.require_project_access",
            side_effect=HTTPException(status_code=403, detail="Access denied"),
        ),
    ):
        r = client.patch(
            "/projects/someone-else/bookings/appointments/bk1", json={"action": "cancel"}
        )
    assert r.status_code == 403
