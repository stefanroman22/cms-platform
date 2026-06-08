from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.models.schemas import UserOut

OWNER = UserOut(id="u1", email="o@acme.com", full_name="O", is_admin=False)
ADMIN = UserOut(id="admin", email="a@x.com", full_name="A", is_admin=True)
PROJECT = {"id": "t1", "name": "Acme", "slug": "acme", "user_id": "u1", "is_active": True}


@pytest.fixture
def client():
    return TestClient(app)


def _auth(user, project=PROJECT):
    # user_via_bearer_or_session and require_project_access are imported INTO booking_admin, patch there.
    return (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=user),
        ),
        patch("auth_service.routers.booking_admin.require_project_access", return_value=project),
    )


def test_get_settings_disabled_when_absent(client):
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_settings", return_value=None
        ),
    ):
        r = client.get("/projects/acme/bookings/settings")
    assert r.status_code == 200 and r.json() == {"enabled": False}


def test_get_settings_enabled(client):
    ru, rp = _auth(OWNER)
    row = {"tenant_id": "t1", "public_slug": "acme", "timezone": "Europe/Berlin"}
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.get_settings", return_value=row
        ),
    ):
        r = client.get("/projects/acme/bookings/settings")
    body = r.json()
    assert body["enabled"] is True and body["public_slug"] == "acme"


def test_enable_requires_admin(client):
    # Non-admin → 403 from admin_user_via_bearer_or_sid (patch it to raise).
    from fastapi import HTTPException

    with patch(
        "auth_service.routers.booking_admin.admin_user_via_bearer_or_sid",
        side_effect=HTTPException(status_code=403, detail="Admin access required"),
    ):
        r = client.post("/projects/acme/bookings/enable")
    assert r.status_code == 403


def test_enable_provisions(client):
    ru, rp = _auth(ADMIN)
    with (
        patch(
            "auth_service.routers.booking_admin.admin_user_via_bearer_or_sid", return_value=ADMIN
        ),
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.owner_email",
            return_value="o@acme.com",
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.provision",
            return_value={"tenant_id": "t1", "public_slug": "acme"},
        ) as prov,
    ):
        r = client.post("/projects/acme/bookings/enable")
    assert r.status_code == 200 and r.json()["enabled"] is True
    prov.assert_called_once()


def test_patch_settings_slug_clash_409(client):
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.slug_taken_by_other",
            return_value=True,
        ),
    ):
        r = client.patch("/projects/acme/bookings/settings", json={"public_slug": "taken"})
    assert r.status_code == 409


def test_services_crud_roundtrip(client):
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "r1"}],
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.insert_service",
            return_value={"id": "s1", "name": "Cut"},
        ),
        patch("auth_service.routers.booking_admin.booking_admin_repo.set_service_resources"),
    ):
        r = client.post(
            "/projects/acme/bookings/services",
            json={"name": "Cut", "duration_min": 45, "resource_ids": ["r1"]},
        )
    assert r.status_code == 201 and r.json()["id"] == "s1"


def test_create_service_rejects_foreign_resource_id(client):
    """SEC-022: linking a resource not owned by the tenant is rejected (no write)."""
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_resources",
            return_value=[{"id": "r1"}],
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.insert_service"
        ) as insert_mock,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.set_service_resources"
        ) as link_mock,
    ):
        r = client.post(
            "/projects/acme/bookings/services",
            json={"name": "Cut", "duration_min": 45, "resource_ids": ["r-foreign"]},
        )
    assert r.status_code == 422
    insert_mock.assert_not_called()
    link_mock.assert_not_called()


def test_delete_service_blocked_when_referenced(client):
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.service_has_bookings",
            return_value=True,
        ),
    ):
        r = client.delete("/projects/acme/bookings/services/s1")
    assert r.status_code == 409


def test_isolation_other_owner_403(client):
    from fastapi import HTTPException

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
        r = client.get("/projects/someone-else/bookings/settings")
    assert r.status_code == 403


def test_get_booking_stats_returns_shape(client):
    from unittest.mock import MagicMock

    ru, rp = _auth(OWNER)
    cfg = MagicMock()
    cfg.timezone = "UTC"
    rows = [
        {"status": "confirmed", "start_utc": "2024-03-15T12:00:00+00:00", "service_name": "Cut"},
        {"status": "cancelled", "start_utc": "2024-03-10T09:00:00+00:00", "service_name": "Color"},
    ]
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_tenant.load_tenant_by_id", return_value=cfg
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.list_bookings_for_stats",
            return_value=rows,
        ),
    ):
        r = client.get("/projects/acme/bookings/stats")
    assert r.status_code == 200
    body = r.json()
    assert "kpis" in body
    assert "by_day" in body
    assert "by_status" in body
    assert body["kpis"]["total"] == 2


# ── Bearer-key path (Connector agent) ────────────────────────────────────────


def test_patch_settings_accepts_bearer_admin_key(client):
    """PATCH /bookings/settings with a Bearer token (Connector agent path).
    user_via_bearer_or_session yields the admin user; no cookie needed."""
    with (
        patch(
            "auth_service.routers.booking_admin.user_via_bearer_or_session",
            new=AsyncMock(return_value=ADMIN),
        ),
        patch("auth_service.routers.booking_admin.require_project_access", return_value=PROJECT),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.slug_taken_by_other",
            return_value=False,
        ),
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.update_settings",
            return_value={"tenant_id": "t1", "timezone": "Europe/Berlin"},
        ) as upd,
    ):
        r = client.patch(
            "/projects/acme/bookings/settings",
            headers={"Authorization": "Bearer testkey"},
            json={"timezone": "Europe/Berlin"},
        )
    assert r.status_code == 200, r.text
    upd.assert_called_once()


def test_patch_settings_widget_color_independent_of_accent(client):
    """widget_color (booking widget) and accent_color (emails) are separate
    columns. Patching both passes both through; patching one leaves the other
    untouched (exclude_unset)."""
    ru, rp = _auth(OWNER)
    with (
        ru,
        rp,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.update_settings",
            return_value={"tenant_id": "t1"},
        ) as upd,
    ):
        r = client.patch(
            "/projects/acme/bookings/settings",
            json={"widget_color": "#c9a961", "accent_color": "#000000"},
        )
    assert r.status_code == 200, r.text
    fields = upd.call_args.args[1]
    assert fields["widget_color"] == "#c9a961"
    assert fields["accent_color"] == "#000000"

    # Patching only the widget color must NOT touch accent_color.
    ru2, rp2 = _auth(OWNER)
    with (
        ru2,
        rp2,
        patch(
            "auth_service.routers.booking_admin.booking_admin_repo.update_settings",
            return_value={"tenant_id": "t1"},
        ) as upd2,
    ):
        r = client.patch("/projects/acme/bookings/settings", json={"widget_color": "#abcdef"})
    assert r.status_code == 200, r.text
    fields2 = upd2.call_args.args[1]
    assert fields2["widget_color"] == "#abcdef"
    assert "accent_color" not in fields2
