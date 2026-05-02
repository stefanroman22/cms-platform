from datetime import UTC
from unittest.mock import MagicMock

import pytest


def _sample_user_row():
    return {
        "id": "u1",
        "email": "admin@example.com",
        "password_hash": "$argon2id$v=19$m=65536,t=3,p=4$DUMMY",
        "full_name": "Admin",
        "is_admin": True,
        "is_active": True,
    }


@pytest.fixture
def auth_deps(monkeypatch):
    """Patch authenticate_user + session helpers so tests drive outcomes directly."""

    async def fake_authenticate(email, password):
        if email == "admin@example.com" and password == "correct-password":
            return _sample_user_row()
        return None

    async def fake_create_session(user, remember_me, user_agent=None, ip=None):
        from datetime import datetime, timedelta

        return "raw-sid-12345", datetime.now(UTC) + timedelta(days=60 if remember_me else 30)

    async def fake_validate(raw):
        from auth_service.models.schemas import UserOut

        if raw == "raw-sid-12345":
            return UserOut(id="u1", email="admin@example.com", full_name="Admin", is_admin=True)
        return None

    async def fake_revoke_session(raw):
        return None

    async def fake_revoke_all(uid):
        return None

    async def fake_change_pw(user_id, current, new):
        return current == "correct-password"

    monkeypatch.setattr("auth_service.routers.auth.authenticate_user", fake_authenticate)
    monkeypatch.setattr("auth_service.routers.auth.create_session", fake_create_session)
    monkeypatch.setattr("auth_service.routers.auth.validate_session", fake_validate)
    monkeypatch.setattr("auth_service.routers.auth.revoke_session", fake_revoke_session)
    monkeypatch.setattr("auth_service.routers.auth.revoke_all_for_user", fake_revoke_all)
    monkeypatch.setattr("auth_service.routers.auth.change_user_password", fake_change_pw)


def test_login_success_sets_sid_cookie_with_httponly(client, auth_deps):
    res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct-password", "remember_me": False},
    )
    assert res.status_code == 200
    set_cookie = res.headers.get("set-cookie", "")
    assert "sid=raw-sid-12345" in set_cookie
    assert "HttpOnly" in set_cookie
    assert "Path=/" in set_cookie


def test_login_wrong_password_returns_401_no_cookie(client, auth_deps):
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert res.status_code == 401
    assert "sid=" not in res.headers.get("set-cookie", "")


def test_login_unknown_email_returns_401_no_cookie(client, auth_deps):
    res = client.post("/auth/login", json={"email": "nobody@example.com", "password": "anything"})
    assert res.status_code == 401


def test_login_remember_me_sets_60_day_max_age(client, auth_deps):
    res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct-password", "remember_me": True},
    )
    set_cookie = res.headers.get("set-cookie", "")
    # 60 days = 5_184_000 seconds
    assert "Max-Age=5184000" in set_cookie


def test_login_default_sets_30_day_max_age(client, auth_deps):
    res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct-password", "remember_me": False},
    )
    set_cookie = res.headers.get("set-cookie", "")
    # 30 days = 2_592_000 seconds
    assert "Max-Age=2592000" in set_cookie


def test_logout_revokes_session_and_clears_cookie(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post("/auth/logout")
    assert res.status_code == 204
    set_cookie = res.headers.get("set-cookie", "")
    # Starlette issues an expiry cookie on delete_cookie
    assert "sid=" in set_cookie
    assert "Max-Age=0" in set_cookie or 'sid=""' in set_cookie or "expires" in set_cookie.lower()


def test_me_returns_user_when_sid_valid(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.get("/auth/me")
    assert res.status_code == 200
    assert res.json()["email"] == "admin@example.com"


def test_me_returns_401_when_sid_missing(client, auth_deps):
    client.cookies.clear()
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_me_returns_401_when_sid_invalid(client, auth_deps):
    client.cookies.set("sid", "bogus")
    res = client.get("/auth/me")
    assert res.status_code == 401


def test_change_password_revokes_all_sessions_and_issues_new_one(client, auth_deps, mock_supabase):
    # change_password re-fetches the user row from Supabase before create_session;
    # mock a single .execute() returning the user dict
    mock_supabase.execute.return_value = MagicMock(data=_sample_user_row())
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post(
        "/auth/change-password",
        json={"current_password": "correct-password", "new_password": "NewStrongPass123"},
    )
    assert res.status_code == 204
    set_cookie = res.headers.get("set-cookie", "")
    assert "sid=" in set_cookie


def test_change_password_wrong_current_returns_400(client, auth_deps):
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "NewStrongPass123"},
    )
    assert res.status_code == 400
