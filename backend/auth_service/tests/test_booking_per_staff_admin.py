"""Tier B — owner-side per-staff config:
- PUT /hours scoped to one barber (resource_id) vs business-wide (null)
- create_resource auto-links the new barber to ALL services (R5 default-all)
- create_service with empty resource_ids defaults to ALL active staff (R5 default-all)
- POST /blocks creates a customer-less personal time-block on a barber's calendar (R4)
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}


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


# ---------- B1: per-resource hours ----------


def test_put_hours_scoped_to_resource(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "staff-A"}],
        ),
        patch("auth_service.routers.booking_admin.booking_admin_repo.replace_hours") as repl,
        patch("auth_service.routers.booking_admin.booking_admin_repo.list_hours", return_value=[]),
    ):
        r = client.put(
            "/projects/acme/bookings/hours",
            json={
                "resource_id": "staff-A",
                "hours": [{"weekday": 3, "start_time": "09:00", "end_time": "17:00"}],
            },
        )
    assert r.status_code == 200, r.text
    repl.assert_called_once()
    assert repl.call_args.kwargs["resource_id"] == "staff-A"


def test_put_hours_business_wide_when_no_resource(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch("auth_service.routers.booking_admin.booking_admin_repo.replace_hours") as repl,
        patch("auth_service.routers.booking_admin.booking_admin_repo.list_hours", return_value=[]),
    ):
        r = client.put(
            "/projects/acme/bookings/hours",
            json={"hours": [{"weekday": 1, "start_time": "09:00", "end_time": "17:00"}]},
        )
    assert r.status_code == 200, r.text
    assert repl.call_args.kwargs["resource_id"] is None


def test_put_hours_rejects_foreign_resource(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "staff-A"}],
        ),
        patch("auth_service.routers.booking_admin.booking_admin_repo.replace_hours") as repl,
    ):
        r = client.put(
            "/projects/acme/bookings/hours",
            json={
                "resource_id": "foreign",
                "hours": [{"weekday": 3, "start_time": "09:00", "end_time": "17:00"}],
            },
        )
    assert r.status_code == 422
    repl.assert_not_called()


# ---------- B3: default-all capability ----------


def test_create_resource_autolinks_all_services(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.insert_resource",
            return_value={"id": "staff-new", "name": "Carol"},
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.link_resource_to_all_services"
        ) as link,
    ):
        r = client.post(
            "/projects/acme/bookings/resources", json={"name": "Carol", "type": "staff"}
        )
    assert r.status_code == 201, r.text
    link.assert_called_once_with("t1", "staff-new")


def test_create_service_defaults_all_resources_when_empty(client):
    ru, rp = _auth()
    captured = {}

    def _set(tenant_id, service_id, resource_ids):
        captured["resource_ids"] = resource_ids

    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[
                {"id": "staff-A", "is_active": True},
                {"id": "staff-B", "is_active": True},
                {"id": "staff-off", "is_active": False},
            ],
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.insert_service",
            return_value={"id": "s9", "name": "Fade"},
        ),
        patch("auth_service.routers.booking_admin.booking_admin_repo.set_service_resources", _set),
    ):
        r = client.post(
            "/projects/acme/bookings/services", json={"name": "Fade", "duration_min": 30}
        )
    assert r.status_code == 201, r.text
    # active staff only, both linked by default
    assert set(captured["resource_ids"]) == {"staff-A", "staff-B"}
    assert set(r.json()["resource_ids"]) == {"staff-A", "staff-B"}


# ---------- B4: personal time-blocks ----------


def test_create_block_inserts_customerless_booking(client):
    ru, rp = _auth()
    captured = {}

    def _insert_block(**kwargs):
        captured.update(kwargs)
        return "blk1"

    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "staff-A"}],
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_block", _insert_block),
        patch("auth_service.routers.booking_admin.booking_repo.insert_audit"),
    ):
        r = client.post(
            "/projects/acme/bookings/blocks",
            json={
                "resource_id": "staff-A",
                "start_utc": "2099-06-10T08:00:00+00:00",
                "end_utc": "2099-06-10T09:00:00+00:00",
                "label": "Lunch",
            },
        )
    assert r.status_code == 201, r.text
    assert r.json()["booking_id"] == "blk1"
    assert captured["resource_id"] == "staff-A"
    assert captured["label"] == "Lunch"


def test_create_block_rejects_foreign_resource(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "staff-A"}],
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_block") as ins,
    ):
        r = client.post(
            "/projects/acme/bookings/blocks",
            json={
                "resource_id": "foreign",
                "start_utc": "2099-06-10T08:00:00+00:00",
                "end_utc": "2099-06-10T09:00:00+00:00",
            },
        )
    assert r.status_code == 422
    ins.assert_not_called()


def test_create_block_rejects_end_before_start(client):
    ru, rp = _auth()
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "staff-A"}],
        ),
        patch("auth_service.routers.booking_admin.booking_repo.insert_block") as ins,
    ):
        r = client.post(
            "/projects/acme/bookings/blocks",
            json={
                "resource_id": "staff-A",
                "start_utc": "2099-06-10T09:00:00+00:00",
                "end_utc": "2099-06-10T08:00:00+00:00",
            },
        )
    assert r.status_code == 422
    ins.assert_not_called()
