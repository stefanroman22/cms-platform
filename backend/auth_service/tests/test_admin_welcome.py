from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app


@pytest.fixture
def client_with_admin(monkeypatch):
    async def fake_dep(request):  # noqa: ARG001
        return {"id": "admin-1", "is_admin": True}

    monkeypatch.setattr("auth_service.routers.workspace.admin_user_via_bearer_or_sid", fake_dep)
    yield TestClient(app)


def _r(data):
    return type("R", (), {"data": data})()


def test_sends_welcome_when_user_exists(client_with_admin):
    with (
        patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb,
        patch("auth_service.routers.workspace.send_welcome_email") as mock_send,
    ):
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r({"id": "u-1", "email": "c@example.com", "full_name": "Client"})
        mock_send.return_value = {"id": "resend_abc"}

        resp = client_with_admin.post(
            "/admin/clients/c@example.com/welcome",
            json={
                "project_slug": "demo",
                "project_name": "Demo Site",
                "website_url": "https://demo.example.com",
            },
        )
        assert resp.status_code == 200
        body = resp.json()
        assert body["success"] is True
        assert body["resend_id"] == "resend_abc"


def test_returns_404_when_user_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r(None)
        resp = client_with_admin.post(
            "/admin/clients/missing@example.com/welcome",
            json={"project_slug": "demo", "project_name": "Demo", "website_url": "https://x"},
        )
        assert resp.status_code == 404


def test_returns_502_on_resend_failure(client_with_admin):
    with (
        patch("auth_service.routers.workspace.get_supabase_admin") as mock_sb,
        patch("auth_service.routers.workspace.send_welcome_email") as mock_send,
    ):
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r({"id": "u-1", "email": "c@example.com", "full_name": "Client"})
        mock_send.side_effect = RuntimeError("Resend 422: bad domain")

        resp = client_with_admin.post(
            "/admin/clients/c@example.com/welcome",
            json={"project_slug": "demo", "project_name": "Demo", "website_url": "https://x"},
        )
        assert resp.status_code == 502
        assert "Resend" in resp.json()["detail"]
