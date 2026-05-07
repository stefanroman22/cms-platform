"""Unit tests for POST /admin/projects."""

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app


@pytest.fixture
def admin_user():
    return {"id": "admin-1", "email": "admin@example.com", "is_admin": True, "is_active": True}


@pytest.fixture
def client_with_admin(admin_user, monkeypatch):
    async def fake_dep(request):  # noqa: ARG001
        return admin_user

    # The endpoint calls admin_user_via_bearer_or_sid directly (not via Depends),
    # so we patch the reference imported into workspace.py.
    monkeypatch.setattr("auth_service.routers.workspace.admin_user_via_bearer_or_sid", fake_dep)
    yield TestClient(app)


def test_creates_project_row_when_owner_exists(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.insert.return_value = sb
        # owner lookup returns user
        sb.execute.side_effect = [
            type("R", (), {"data": {"id": "owner-1", "email": "c@e"}})(),
            # slug uniqueness check returns None
            type("R", (), {"data": None})(),
            # insert returns row
            type("R", (), {"data": [{"id": "p1", "slug": "demo", "name": "Demo"}]})(),
        ]
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "c@example.com"},
        )
        assert resp.status_code == 201, resp.text
        assert resp.json()["slug"] == "demo"


def test_returns_404_when_owner_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = type("R", (), {"data": None})()
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "missing@example.com"},
        )
        assert resp.status_code == 404


def test_returns_409_when_slug_exists(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.side_effect = [
            type("R", (), {"data": {"id": "owner-1"}})(),
            type("R", (), {"data": {"id": "p-existing", "slug": "demo"}})(),
        ]
        resp = client_with_admin.post(
            "/admin/projects",
            json={"slug": "demo", "name": "Demo", "owner_email": "c@example.com"},
        )
        assert resp.status_code == 409
