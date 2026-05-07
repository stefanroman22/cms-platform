"""Rate-limit integration tests.

Run only against a freshly-deployed backend where the per-IP bucket is
empty. The deployed slowapi limiter resets on cold-start, so these
tests are inherently flaky if a previous run filled the bucket — gate
each test on its own bucket-isolation strategy.

The CI runner shares an outbound IP across all jobs, so we use unique
`X-Forwarded-For` per test to land in different buckets.
"""

import os
import secrets

import httpx
import pytest

pytestmark = pytest.mark.integration

BACKEND_URL = os.environ.get("E2E_BASE_URL_BACKEND", "https://cms-backend-roman.vercel.app")


def _fresh_ip() -> str:
    """Random IP-like string in the 198.51.100.0/24 documentation range so
    each test uses an isolated rate-limit bucket without colliding with real
    traffic or other tests."""
    return f"198.51.100.{secrets.randbelow(254) + 1}"


def test_login_rate_limit_fires_at_11th_request():
    """After 10 successful or failed login attempts inside 1 minute,
    the 11th must be blocked with HTTP 429. Spec: 10/minute per IP."""
    fwd = _fresh_ip()
    headers = {"Content-Type": "application/json", "X-Forwarded-For": fwd}
    body = {"email": "rate-limit-probe@cms-test.dev", "password": "wrong-on-purpose"}

    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
        # First 10 should be 401 (bad creds), not 429.
        for i in range(10):
            r = c.post("/auth/login", json=body, headers=headers)
            assert (
                r.status_code == 401
            ), f"attempt {i + 1}: expected 401, got {r.status_code} body={r.text}"

        # 11th must be 429 (limiter triggered).
        r = c.post("/auth/login", json=body, headers=headers)
        assert (
            r.status_code == 429
        ), f"11th attempt: expected 429, got {r.status_code} body={r.text}"


def test_login_rate_limit_isolated_per_ip():
    """A second IP arriving fresh after the first IP burned its bucket
    should still be allowed up to its own quota."""
    burned_ip = _fresh_ip()
    fresh_ip = _fresh_ip()
    body = {"email": "rate-limit-probe@cms-test.dev", "password": "wrong-on-purpose"}

    with httpx.Client(base_url=BACKEND_URL, timeout=15.0) as c:
        # Burn the first IP.
        for _ in range(11):
            c.post(
                "/auth/login",
                json=body,
                headers={"Content-Type": "application/json", "X-Forwarded-For": burned_ip},
            )

        # Fresh IP — first attempt must still be 401, not 429.
        r = c.post(
            "/auth/login",
            json=body,
            headers={"Content-Type": "application/json", "X-Forwarded-For": fresh_ip},
        )
        assert (
            r.status_code == 401
        ), f"fresh IP first attempt: expected 401, got {r.status_code} body={r.text}"
