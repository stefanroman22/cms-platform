"""Shared HTTP client + login fixtures for integration tests.

Tests in this directory hit the DEPLOYED backend. They use the dedicated
E2E test users created by scripts/seed_e2e.py.
"""

from __future__ import annotations

import os

import httpx
import pytest

BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
E2E_USER_EMAIL = os.environ["E2E_USER_EMAIL"]
E2E_USER_PASSWORD = os.environ["E2E_USER_PASSWORD"]
E2E_ADMIN_EMAIL = os.environ["E2E_ADMIN_EMAIL"]
E2E_ADMIN_PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]


pytestmark = pytest.mark.integration


@pytest.fixture
def client() -> httpx.Client:
    """Bare HTTP client (no cookies). For public endpoints + auth flow tests."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
        yield c


def _login(c: httpx.Client, email: str, password: str) -> None:
    r = c.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert "sid" in r.cookies


@pytest.fixture
def user_client() -> httpx.Client:
    """HTTP client logged in as the regular E2E user."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
        _login(c, E2E_USER_EMAIL, E2E_USER_PASSWORD)
        yield c


@pytest.fixture
def admin_client() -> httpx.Client:
    """HTTP client logged in as the admin E2E user."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
        _login(c, E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD)
        yield c
