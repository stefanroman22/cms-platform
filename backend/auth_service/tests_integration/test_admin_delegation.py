"""End-to-end test: create + transfer + welcome roundtrip against the
deployed backend, using the admin Bearer key."""

import os
import time

import httpx
import pytest

pytestmark = pytest.mark.integration

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
    # Cleanup: PATCH is_active=false (soft-delete on this schema).
    httpx.request(
        "PATCH",
        f"{BACKEND}/admin/projects/{slug}",
        json={"is_active": False},
        headers=HEADERS,
        timeout=15.0,
    )


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
