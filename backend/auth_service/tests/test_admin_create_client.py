"""Unit tests for POST /admin/clients.

These regression-test the fix that drops the parallel
`sb_admin.auth.admin.create_user` call (which orphaned auth.users rows)
and instead writes an argon2 password_hash on the public.users insert.
"""

from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from auth_service.main import app
from auth_service.services.auth_service import verify_password


@pytest.fixture
def client_with_admin(monkeypatch):
    async def fake_dep(request):  # noqa: ARG001
        return {"id": "admin-1", "is_admin": True}

    monkeypatch.setattr("auth_service.routers.workspace.admin_user_via_bearer_or_sid", fake_dep)
    yield TestClient(app)


def _r(data):
    return type("R", (), {"data": data})()


def _build_mock(lookup_data):
    """One chainable mock that handles BOTH the lookup chain
    (`.table.select.eq.limit.execute`) and the insert chain
    (`.table.insert.execute`). Side effect on `.execute()` returns the
    lookup result first, then `_r(None)` for the subsequent insert."""
    sb = MagicMock()
    for m in ("table", "select", "eq", "limit", "insert"):
        getattr(sb, m).return_value = sb
    sb.execute.side_effect = [_r(lookup_data), _r(None)]
    return sb


def test_creates_user_with_password_hash(client_with_admin):
    """New email → public.users insert payload contains a non-empty password_hash,
    and sb.auth.admin.create_user is NEVER called."""
    sb = _build_mock(lookup_data=[])

    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post(
            "/admin/clients",
            json={"email": "new-client@example.com", "full_name": "New Client"},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] is True
    assert body["generated_password"] is not None
    assert body["email"] == "new-client@example.com"

    # Capture the .insert(...) payload sent to public.users.
    sb.insert.assert_called_once()
    insert_payload = sb.insert.call_args[0][0]
    assert "password_hash" in insert_payload
    assert insert_payload["password_hash"]  # non-empty string
    assert insert_payload["email"] == "new-client@example.com"
    assert insert_payload["is_active"] is True

    # Supabase Auth admin API must NOT be touched — Phase B path is gone.
    sb.auth.admin.create_user.assert_not_called()


def test_returns_existing_user_without_password(client_with_admin):
    """Existing email → returns row with created=False, no generated_password,
    and never inserts."""
    sb = _build_mock(
        lookup_data=[{"id": "existing-1", "email": "existing@example.com", "full_name": "Existing"}]
    )

    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post(
            "/admin/clients",
            json={"email": "existing@example.com", "full_name": "Existing"},
        )

    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["created"] is False
    assert body["generated_password"] is None
    assert body["id"] == "existing-1"
    assert body["email"] == "existing@example.com"

    # Existing branch must not call insert / auth.admin.create_user.
    sb.insert.assert_not_called()
    sb.auth.admin.create_user.assert_not_called()


def test_generated_password_verifies_against_stored_hash(client_with_admin):
    """The hash written to public.users must verify against the password
    returned to the admin caller — i.e. login will work afterwards."""
    sb = _build_mock(lookup_data=[])

    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post(
            "/admin/clients",
            json={"email": "verify-pw@example.com", "full_name": None},
        )

    assert resp.status_code == 201, resp.text
    returned_password = resp.json()["generated_password"]
    assert returned_password

    captured_hash = sb.insert.call_args[0][0]["password_hash"]
    assert verify_password(returned_password, captured_hash) is True
