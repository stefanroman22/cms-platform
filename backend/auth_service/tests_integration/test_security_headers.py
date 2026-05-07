"""Security-headers regression tests.

Probes the deployed frontend (Next.js) and backend (FastAPI) and asserts
the headers required by FE-001 / INFRA-001 / INFRA-002 are present.

Marked `deployed_state` because the headers come from a Vercel deploy
that lags behind a `dev` push by ~2 minutes (and does not happen at all
for branches other than master). Running on dev push always sees the
PREVIOUS deploy's headers, drowning real regressions in noise.

Run path:
- dev push: skipped via `-m "integration and not deployed_state"`.
- master push: runs after a deploy-wait gate in e2e.yml.
"""

import os

import httpx
import pytest

# `deployed_state` because Vercel deploys prod only on master push.
pytestmark = [pytest.mark.integration, pytest.mark.deployed_state]

FRONTEND_URL = os.environ.get("E2E_BASE_URL_FRONTEND", "https://roman-technologies.dev")
BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")


REQUIRED_FRONTEND_HEADERS = {
    "strict-transport-security": "max-age=",
    "x-content-type-options": "nosniff",
    "x-frame-options": "DENY",
    "referrer-policy": "strict-origin-when-cross-origin",
    "permissions-policy": "camera=()",
    "content-security-policy": "frame-ancestors 'none'",
}


def test_frontend_serves_security_headers_on_dashboard():
    """Dashboard / page must carry the full security-header set."""
    r = httpx.get(f"{FRONTEND_URL}/log-in", timeout=15.0, follow_redirects=True)
    assert r.status_code == 200, r.text[:200]
    for name, expected_substring in REQUIRED_FRONTEND_HEADERS.items():
        actual = r.headers.get(name, "")
        assert expected_substring in actual, (
            f"missing/bad header `{name}`: expected to contain "
            f"'{expected_substring}', got '{actual}'"
        )


def test_frontend_csp_blocks_framing():
    """CSP must explicitly forbid embedding (frame-ancestors 'none' or DENY).
    This is the click-jacking gate."""
    r = httpx.get(f"{FRONTEND_URL}/log-in", timeout=15.0, follow_redirects=True)
    csp = r.headers.get("content-security-policy", "")
    xfo = r.headers.get("x-frame-options", "")
    assert (
        "frame-ancestors 'none'" in csp or xfo == "DENY"
    ), f"frame-ancestors not denied; csp='{csp}' xfo='{xfo}'"


def test_backend_health_carries_minimum_headers():
    """Backend `/health` must at least nosniff + DENY framing.
    HSTS is checked separately because Vercel sometimes adds it for the
    edge layer when the function is on a custom domain."""
    r = httpx.get(f"{BACKEND_URL}/health", timeout=15.0)
    assert r.status_code == 200
    assert (
        r.headers.get("x-content-type-options") == "nosniff"
    ), f"backend missing X-Content-Type-Options: nosniff, got {r.headers.get('x-content-type-options')}"
    assert (
        r.headers.get("x-frame-options") == "DENY"
    ), f"backend missing X-Frame-Options: DENY, got {r.headers.get('x-frame-options')}"
