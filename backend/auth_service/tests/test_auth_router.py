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
    # Isolate login tests from the Postgres login-lockout limiter (SEC-011).
    monkeypatch.setattr("auth_service.core.pg_rate_limit.over_limit", lambda *a, **k: False)
    monkeypatch.setattr("auth_service.core.pg_rate_limit.allow", lambda *a, **k: True)
    monkeypatch.setattr("auth_service.core.pg_rate_limit.reset", lambda *a, **k: None)


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


def test_login_normalizes_email_case_and_whitespace(client, auth_deps):
    """A phone auto-capitalizing the address (or a copy-paste with spaces) must
    still log in: LoginRequest lowercases + strips the email before it reaches
    authenticate_user. Regression for the 2026-08 client lockout."""
    res = client.post(
        "/auth/login",
        json={"email": "  ADMIN@Example.COM  ", "password": "correct-password"},
    )
    assert res.status_code == 200
    assert "sid=raw-sid-12345" in res.headers.get("set-cookie", "")


def test_login_strips_password_whitespace(client, auth_deps):
    """Trailing whitespace from copy-pasting the password out of an HTML email
    must not fail the login."""
    res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "  correct-password\n"},
    )
    assert res.status_code == 200


def test_authenticate_user_normalizes_email(monkeypatch):
    """Service-level defense: authenticate_user lowercases + strips the email in
    its own SELECT, so non-router callers get the same behaviour."""
    import asyncio

    from auth_service.services import auth_service as svc

    sb = MagicMock()
    for m in ("table", "select", "eq", "maybe_single"):
        getattr(sb, m).return_value = sb
    sb.execute.return_value = MagicMock(data=None)
    monkeypatch.setattr(svc, "get_supabase_admin", lambda: sb)

    asyncio.run(svc.authenticate_user("  MiXed@Case.COM  ", "pw"))
    email_eq = sb.eq.call_args_list[0]
    assert email_eq.args == ("email", "mixed@case.com")


def test_generated_password_alphabet_has_no_ambiguous_chars():
    """Generated passwords are hand-typed by clients from an email: exclude
    glyphs that misread (l/I/1, O/0) and characters that HTML email clients
    mangle (& < > \" ')."""
    from auth_service.routers.workspace import _PASSWORD_ALPHABET, _generate_password

    forbidden = set("lI1O0&<>\"'")
    assert not (set(_PASSWORD_ALPHABET) & forbidden)
    pw = _generate_password()
    assert len(pw) == 16
    assert not (set(pw) & forbidden)


def test_login_locked_account_returns_429(client, auth_deps, monkeypatch):
    """SEC-011: once the per-account failure threshold is crossed, login is refused."""
    monkeypatch.setattr("auth_service.core.pg_rate_limit.over_limit", lambda *a, **k: True)
    res = client.post(
        "/auth/login",
        json={"email": "admin@example.com", "password": "correct-password"},
    )
    assert res.status_code == 429
    assert "sid=" not in res.headers.get("set-cookie", "")


def test_login_failure_registers_attempt(client, auth_deps, monkeypatch):
    """SEC-011: a wrong password counts against the account's failure budget."""
    calls = []
    monkeypatch.setattr(
        "auth_service.core.pg_rate_limit.allow",
        lambda bucket, *a, **k: calls.append(bucket) or True,
    )
    res = client.post("/auth/login", json={"email": "admin@example.com", "password": "wrong"})
    assert res.status_code == 401
    assert calls == ["login_fail:admin@example.com"]


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


@pytest.fixture
def fresh_limiter():
    """/auth/change-password is limited to 3/minute; the notice tests below
    would otherwise trip it after the earlier change-password tests."""
    from auth_service.core.limiter import limiter

    limiter.reset()
    yield
    limiter.reset()


def test_change_password_sends_security_notice(
    client, auth_deps, mock_supabase, monkeypatch, fresh_limiter
):
    sent = []
    monkeypatch.setattr(
        "auth_service.routers.auth.send_password_changed_email",
        lambda **kw: sent.append(kw),
    )
    mock_supabase.execute.return_value = MagicMock(data=_sample_user_row())
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post(
        "/auth/change-password",
        json={"current_password": "correct-password", "new_password": "NewStrongPass123"},
    )
    assert res.status_code == 204
    assert sent == [{"to_email": "admin@example.com", "reason": "self_service"}]


def test_change_password_succeeds_when_notice_fails(
    client, auth_deps, mock_supabase, monkeypatch, fresh_limiter
):
    def boom(**_kw):
        raise RuntimeError("Resend 500")

    monkeypatch.setattr("auth_service.routers.auth.send_password_changed_email", boom)
    mock_supabase.execute.return_value = MagicMock(data=_sample_user_row())
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post(
        "/auth/change-password",
        json={"current_password": "correct-password", "new_password": "NewStrongPass123"},
    )
    assert res.status_code == 204


def test_change_password_wrong_current_sends_no_notice(
    client, auth_deps, monkeypatch, fresh_limiter
):
    sent = []
    monkeypatch.setattr(
        "auth_service.routers.auth.send_password_changed_email",
        lambda **kw: sent.append(kw),
    )
    client.cookies.set("sid", "raw-sid-12345")
    res = client.post(
        "/auth/change-password",
        json={"current_password": "wrong", "new_password": "NewStrongPass123"},
    )
    assert res.status_code == 400
    assert sent == []
