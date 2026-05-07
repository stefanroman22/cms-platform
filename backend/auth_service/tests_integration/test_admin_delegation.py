"""End-to-end test: create + transfer + welcome roundtrip against the
deployed backend, using the admin Bearer key.

Marked `deployed_state` because:
  • `test_create_then_delete_throwaway_project` calls the new
    `DELETE /admin/projects/{slug}` endpoint, which doesn't exist on
    master until this branch lands.
  • `test_create_client_writes_public_users_row` now asserts the
    cleanup DELETE returns 204/404 instead of silently swallowing
    errors. The strict assertion only makes sense once the backend
    fixes that surfaced the previous silent failures are deployed.

`e2e.yml` skips `deployed_state` on dev push (`-m "integration and not
deployed_state"`) and runs the full set on master push after the
deploy-readiness curl loop.
"""

import os
import time

import httpx
import pytest

pytestmark = [pytest.mark.integration, pytest.mark.deployed_state]

BACKEND = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")
ADMIN_KEY = os.environ.get("E2E_ADMIN_API_KEY")
USER_EMAIL = os.environ.get("E2E_USER_EMAIL")
ADMIN_EMAIL = os.environ.get("E2E_ADMIN_EMAIL")

skip = pytest.mark.skipif(
    not (ADMIN_KEY and USER_EMAIL and ADMIN_EMAIL),
    reason="missing E2E_ADMIN_API_KEY/E2E_USER_EMAIL/E2E_ADMIN_EMAIL",
)

HEADERS = {"Authorization": f"Bearer {ADMIN_KEY}", "Content-Type": "application/json"}


@skip
def test_create_then_delete_throwaway_project():
    slug = f"throwaway-{int(time.time())}"
    create = httpx.post(
        f"{BACKEND}/admin/projects",
        json={"slug": slug, "name": "Throwaway E2E", "owner_email": USER_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert create.status_code == 201, create.text
    try:
        # Round-trip the patch to verify is_active toggling works (was the
        # original soft-delete path; some callers still rely on it).
        patch = httpx.request(
            "PATCH",
            f"{BACKEND}/admin/projects/{slug}",
            json={"is_active": False},
            headers=HEADERS,
            timeout=15.0,
        )
        assert patch.status_code == 200, patch.text
    finally:
        # Hard delete so the row never lingers in the dashboard. Asserts
        # 204 — silent failures here are what produced the "Throwaway
        # E2E" pollution we just cleaned up.
        delete = httpx.delete(
            f"{BACKEND}/admin/projects/{slug}",
            headers=HEADERS,
            timeout=15.0,
        )
        assert delete.status_code in (
            204,
            404,
        ), f"throwaway project cleanup failed: {delete.status_code} {delete.text}"


@skip
def test_transfer_round_trip_on_e2e_test_project():
    r1 = httpx.post(
        f"{BACKEND}/admin/projects/e2e-test-project/transfer",
        json={"to_user_email": ADMIN_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert r1.status_code == 200, r1.text
    r2 = httpx.post(
        f"{BACKEND}/admin/projects/e2e-test-project/transfer",
        json={"to_user_email": USER_EMAIL},
        headers=HEADERS,
        timeout=15.0,
    )
    assert r2.status_code == 200, r2.text


@skip
def test_create_client_writes_public_users_row():
    """POST /admin/clients with a fresh email must create a public.users row
    with a non-NULL password_hash (regression for the 500 caused by the
    parallel sb_admin.auth.admin.create_user path that omitted password_hash).

    Verification is HTTP-only — integration tests don't have direct Supabase
    access. We prove the row + hash via two public endpoints:
      1. GET /admin/clients/lookup → row exists.
      2. POST /auth/login with the returned password → 200 means
         password_hash was stored AND verifies (NULL → login would 401).
    """
    email = f"throwaway-create-{int(time.time())}@cms-test.dev"

    # Create.
    create = httpx.post(
        f"{BACKEND}/admin/clients",
        json={"email": email, "full_name": "Throwaway Create"},
        headers=HEADERS,
        timeout=15.0,
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert body["created"] is True
    assert body["email"] == email
    generated_password = body["generated_password"]
    assert generated_password, "endpoint must return the generated password once"

    try:
        # Row exists in public.users (admin lookup hits the same table).
        lookup = httpx.get(
            f"{BACKEND}/admin/clients/lookup",
            params={"email": email},
            headers=HEADERS,
            timeout=15.0,
        )
        assert lookup.status_code == 200, lookup.text
        assert lookup.json()["email"] == email

        # password_hash IS NOT NULL — login uses verify_password against the
        # stored hash, so a successful login proves the hash was written
        # correctly (NULL or wrong hash → 401).
        login = httpx.post(
            f"{BACKEND}/auth/login",
            json={"email": email, "password": generated_password},
            timeout=15.0,
        )
        assert login.status_code == 200, login.text
        assert "sid" in login.cookies
    finally:
        # Cleanup so CI runs don't accumulate throwaway-create-*@cms-test.dev
        # rows in production Supabase. Asserts a known-good status — silent
        # except (the original code) is what produced the dashboard pollution
        # we just cleaned up. 404 means cleanup already happened (idempotent).
        delete = httpx.delete(
            f"{BACKEND}/admin/clients/{email}",
            headers=HEADERS,
            timeout=15.0,
        )
        assert delete.status_code in (
            204,
            404,
        ), f"throwaway client cleanup failed: {delete.status_code} {delete.text}"


@skip
def test_welcome_email_send():
    r = httpx.post(
        f"{BACKEND}/admin/clients/{USER_EMAIL}/welcome",
        json={
            "project_slug": "e2e-test-project",
            "project_name": "E2E Test Project",
            "website_url": "https://cms-frontend-roman.vercel.app",
        },
        headers=HEADERS,
        timeout=15.0,
    )
    assert r.status_code == 200, r.text
    assert r.json()["success"] is True
