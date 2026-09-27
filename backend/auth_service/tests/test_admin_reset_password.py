"""Unit tests for POST /admin/clients/{email}/reset-password.

Admin-triggered credential recovery: generates a fresh password, argon2-hashes
it onto public.users, revokes every live session for the user, and returns the
password exactly once. Added 2026-08-26 after a client was stranded with a
pre-054478e credential and no reset path existed at all.
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


@pytest.fixture
def client_without_admin(monkeypatch):
    async def fake_dep(request):  # noqa: ARG001
        from fastapi import HTTPException

        raise HTTPException(status_code=403, detail="Admin access required")

    monkeypatch.setattr("auth_service.routers.workspace.admin_user_via_bearer_or_sid", fake_dep)
    yield TestClient(app)


def _r(data):
    return type("R", (), {"data": data})()


def _build_mock(lookup_data):
    """Chainable mock handling the lookup (`.table.select.eq.limit.execute`)
    and the update (`.table.update.eq.execute`) chains. `.execute()` returns
    the lookup result first, then `_r(None)` for the update."""
    sb = MagicMock()
    for m in ("table", "select", "eq", "limit", "update"):
        getattr(sb, m).return_value = sb
    sb.execute.side_effect = [_r(lookup_data), _r(None)]
    return sb


def test_reset_password_403_for_non_admin(client_without_admin):
    resp = client_without_admin.post("/admin/clients/someone@example.com/reset-password")
    assert resp.status_code == 403


def test_reset_password_404_for_unknown_email(client_with_admin):
    sb = _build_mock(lookup_data=[])
    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post("/admin/clients/nobody@example.com/reset-password")
    assert resp.status_code == 404


def test_reset_password_writes_hash_revokes_sessions_returns_password(
    client_with_admin, monkeypatch
):
    revoked = []

    async def fake_revoke_all(uid):
        revoked.append(uid)

    monkeypatch.setattr("auth_service.routers.workspace.revoke_all_for_user", fake_revoke_all)

    sb = _build_mock(
        lookup_data=[{"id": "u-9", "email": "george@example.com", "full_name": "George"}]
    )
    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post("/admin/clients/GEORGE@Example.com/reset-password")

    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["email"] == "george@example.com"
    password = body["generated_password"]
    assert password

    # Lookup used the normalized email.
    lookup_eq = sb.eq.call_args_list[0]
    assert lookup_eq.args == ("email", "george@example.com")

    # The stored hash verifies against the returned password (login will work).
    sb.update.assert_called_once()
    update_payload = sb.update.call_args[0][0]
    assert set(update_payload) == {"password_hash"}
    assert verify_password(password, update_payload["password_hash"]) is True

    # Every live session dies with the old credential.
    assert revoked == ["u-9"]


def test_reset_password_notifies_client_without_the_password(client_with_admin, monkeypatch):
    async def fake_revoke_all(uid):  # noqa: ARG001
        return None

    sent = []
    monkeypatch.setattr("auth_service.routers.workspace.revoke_all_for_user", fake_revoke_all)
    monkeypatch.setattr(
        "auth_service.routers.workspace.send_password_changed_email",
        lambda **kw: sent.append(kw),
    )
    sb = _build_mock(
        lookup_data=[{"id": "u-9", "email": "george@example.com", "full_name": "George"}]
    )
    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post("/admin/clients/george@example.com/reset-password")

    assert resp.status_code == 200
    assert sent == [{"to_email": "george@example.com", "reason": "admin_reset"}]
    # The generated password is only in the admin's API response, never in the email call.
    assert resp.json()["generated_password"] not in repr(sent)


def test_reset_password_still_returns_password_when_notice_fails(client_with_admin, monkeypatch):
    async def fake_revoke_all(uid):  # noqa: ARG001
        return None

    def boom(**_kw):
        raise RuntimeError("Resend 500")

    monkeypatch.setattr("auth_service.routers.workspace.revoke_all_for_user", fake_revoke_all)
    monkeypatch.setattr("auth_service.routers.workspace.send_password_changed_email", boom)
    sb = _build_mock(
        lookup_data=[{"id": "u-9", "email": "george@example.com", "full_name": "George"}]
    )
    with patch("auth_service.routers.workspace.get_supabase_admin", return_value=sb):
        resp = client_with_admin.post("/admin/clients/george@example.com/reset-password")

    assert resp.status_code == 200
    assert resp.json()["generated_password"]
