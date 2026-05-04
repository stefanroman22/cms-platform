import os

import pytest

pytestmark = pytest.mark.integration

EMAIL = os.environ["E2E_USER_EMAIL"]
PASSWORD = os.environ["E2E_USER_PASSWORD"]


def test_login_success_sets_sid_cookie(client):
    r = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    assert r.status_code == 200
    assert "sid" in r.cookies
    sid = r.cookies["sid"]
    assert len(sid) > 20


def test_me_returns_user_when_authenticated(user_client):
    r = user_client.get("/auth/me")
    assert r.status_code == 200
    data = r.json()
    assert data["email"] == EMAIL
    assert data["is_admin"] is False


def test_me_returns_401_without_sid(client):
    r = client.get("/auth/me")
    assert r.status_code == 401


def test_login_with_wrong_email_returns_401(client):
    r = client.post(
        "/auth/login",
        json={"email": "no-such-user@cms-test.dev", "password": "x"},
    )
    assert r.status_code == 401
    assert "Invalid email or password" in r.text


def test_login_with_wrong_password_returns_401(client):
    r = client.post(
        "/auth/login",
        json={"email": EMAIL, "password": "wrong"},
    )
    assert r.status_code == 401


def test_logout_invalidates_session(client):
    lr = client.post("/auth/login", json={"email": EMAIL, "password": PASSWORD})
    sid = lr.cookies["sid"]
    logout = client.post("/auth/logout")
    assert logout.status_code == 204
    me = client.get("/auth/me", cookies={"sid": sid})
    assert me.status_code == 401
