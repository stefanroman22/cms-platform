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


def test_transfers_ownership(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.update.return_value = sb
        sb.execute.side_effect = [
            _r({"id": "newowner-1", "email": "new@example.com"}),
            _r([{"id": "p1", "slug": "demo", "user_id": "newowner-1"}]),
        ]
        resp = client_with_admin.post(
            "/admin/projects/demo/transfer",
            json={"to_user_email": "new@example.com"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["user_id"] == "newowner-1"


def test_404_when_target_user_missing(client_with_admin):
    with patch("auth_service.routers.workspace.get_supabase") as mock_sb:
        sb = mock_sb.return_value
        sb.table.return_value = sb
        sb.select.return_value = sb
        sb.eq.return_value = sb
        sb.maybe_single.return_value = sb
        sb.execute.return_value = _r(None)
        resp = client_with_admin.post(
            "/admin/projects/demo/transfer",
            json={"to_user_email": "nobody@example.com"},
        )
        assert resp.status_code == 404
