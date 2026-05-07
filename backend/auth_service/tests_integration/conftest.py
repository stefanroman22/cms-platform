"""Shared HTTP client + login fixtures for integration tests.

Tests in this directory hit the DEPLOYED backend. They use the dedicated
E2E test users created by scripts/seed_e2e.py.

Rate-limit isolation
---------------------
The deployed backend extracts the client IP from X-Forwarded-For
(BE-002). All E2E jobs run from the SAME GitHub-runner outbound IP, so
without per-test X-Forwarded-For override every login goes into the
same 10/min bucket and the suite hits 429 mid-run.

Each fixture below stamps a fresh IP from the documentation range
198.51.100.0/24 onto every request, giving each test its own bucket.
The deployed slowapi resolves keys per-request, so this keeps tests
parallel-safe and bucket-isolated.
"""

from __future__ import annotations

import os
import secrets

import httpx
import pytest

BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
E2E_USER_EMAIL = os.environ["E2E_USER_EMAIL"]
E2E_USER_PASSWORD = os.environ["E2E_USER_PASSWORD"]
E2E_ADMIN_EMAIL = os.environ["E2E_ADMIN_EMAIL"]
E2E_ADMIN_PASSWORD = os.environ["E2E_ADMIN_PASSWORD"]


pytestmark = pytest.mark.integration


def _fresh_xff() -> dict[str, str]:
    """Per-test X-Forwarded-For so each test lands in its own
    rate-limit bucket. Documentation range, never collides with real
    routable traffic."""
    return {"X-Forwarded-For": f"198.51.100.{secrets.randbelow(254) + 1}"}


@pytest.fixture
def client() -> httpx.Client:
    """Bare HTTP client (no cookies). For public endpoints + auth flow tests."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0, headers=_fresh_xff()) as c:
        yield c


def _login(c: httpx.Client, email: str, password: str) -> None:
    r = c.post("/auth/login", json={"email": email, "password": password})
    assert r.status_code == 200, f"login failed: {r.status_code} {r.text}"
    assert "sid" in r.cookies


@pytest.fixture
def user_client() -> httpx.Client:
    """HTTP client logged in as the regular E2E user."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0, headers=_fresh_xff()) as c:
        _login(c, E2E_USER_EMAIL, E2E_USER_PASSWORD)
        yield c


@pytest.fixture
def admin_client() -> httpx.Client:
    """HTTP client logged in as the admin E2E user."""
    with httpx.Client(base_url=BACKEND_URL, timeout=15.0, headers=_fresh_xff()) as c:
        _login(c, E2E_ADMIN_EMAIL, E2E_ADMIN_PASSWORD)
        yield c
