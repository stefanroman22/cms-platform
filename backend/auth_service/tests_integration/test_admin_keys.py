"""Integration tests against the deployed backend for the admin Bearer
auth path. Gated by E2E_ADMIN_API_KEY (a real key minted from prod
Supabase, stored as a GitHub Actions secret)."""

import os

import httpx
import pytest

pytestmark = pytest.mark.integration

BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
ADMIN_KEY = os.environ.get("E2E_ADMIN_API_KEY")

skip_if_no_key = pytest.mark.skipif(
    not ADMIN_KEY,
    reason="E2E_ADMIN_API_KEY not set; mint one and set the secret",
)


@skip_if_no_key
def test_bearer_admin_lists_projects():
    r = httpx.get(
        f"{BACKEND_URL}/admin/projects",
        headers={"Authorization": f"Bearer {ADMIN_KEY}"},
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert isinstance(body, list)
    slugs = {p["slug"] for p in body}
    assert "e2e-test-project" in slugs


@skip_if_no_key
def test_bad_bearer_returns_401():
    r = httpx.get(
        f"{BACKEND_URL}/admin/projects",
        headers={
            "Authorization": "Bearer cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
        },
        timeout=15.0,
    )
    assert r.status_code == 401


def test_no_auth_returns_401():
    r = httpx.get(f"{BACKEND_URL}/admin/projects", timeout=15.0)
    assert r.status_code == 401
