"""Pinned defaults + invariants for `auth_service.core.config.Settings`.

These tests are what stops a future config drift from silently breaking
production: wrong email from-domain (parked → 403 from Resend), unrecognised
ENVIRONMENT value (silently routes through prod path), or missing
FRONTEND_ORIGINS in prod (silent CORS fallback to localhost-only).
"""

import pytest
from pydantic import ValidationError

from auth_service.core.config import Settings


def _baseline_env(monkeypatch) -> None:
    """Provide the minimum required env to instantiate Settings without
    the on-disk .env file leaking into the test."""
    for k in [
        "RESEND_FROM_EMAIL",
        "RESEND_API_KEY",
        "FRONTEND_ORIGINS",
        "ENVIRONMENT",
    ]:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setenv("SUPABASE_ANON_KEY", "dummy-anon")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "dummy-service-role")


def test_resend_from_email_default_uses_verified_domain(monkeypatch):
    """The legacy default (`noreply@romantechnologies.com`) pointed at a
    parked domain and would 403 every email Resend tried to send. The new
    default uses the verified `roman-technologies.dev` domain."""
    _baseline_env(monkeypatch)
    s = Settings(_env_file=None)
    assert s.RESEND_FROM_EMAIL == "noreply@roman-technologies.dev"


# ── ENVIRONMENT must be one of the three known tiers ──────────────────────


def test_environment_must_be_one_of_three_tiers(monkeypatch):
    """ENVIRONMENT used to be `str`, so `prod` / `PRODUCTION` / `''` /
    typos all silently flowed through the production code path. It is now
    typed as Literal["development", "preview", "production"] — Pydantic
    rejects anything else at startup."""
    _baseline_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "prod")
    with pytest.raises(ValidationError):
        Settings(_env_file=None)


def test_environment_accepts_preview_tier(monkeypatch):
    """Vercel preview deployments need their own tier so we don't have
    to choose between dev-permissive CORS or prod-strict CORS."""
    _baseline_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "preview")
    s = Settings(_env_file=None)
    assert s.ENVIRONMENT == "preview"


# ── FRONTEND_ORIGINS must be set in production ────────────────────────────


def test_frontend_origins_required_in_production(monkeypatch):
    """If FRONTEND_ORIGINS is missing in production the backend used to
    silently fall back to localhost-only origins, which 403s every real
    frontend with an opaque CORS error in the browser console. Fail loud
    at startup instead."""
    _baseline_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("FRONTEND_ORIGINS", "")
    with pytest.raises(ValidationError, match="FRONTEND_ORIGINS"):
        Settings(_env_file=None)


def test_frontend_origins_optional_in_development(monkeypatch):
    """Local dev keeps the localhost default — no setup ceremony for new
    contributors."""
    _baseline_env(monkeypatch)
    monkeypatch.setenv("ENVIRONMENT", "development")
    s = Settings(_env_file=None)
    assert "localhost" in s.FRONTEND_ORIGINS


# ── SUPABASE_SERVICE_ROLE_KEY must be set in preview/production (INFRA-007) ──


def test_service_role_required_in_production(monkeypatch):
    """Closes INFRA-007. Production without service-role key would silently
    fall back to the anon client — every admin endpoint returns zero rows
    (RLS-enabled tables) with an opaque 200 response. Fail-loud at startup."""
    _baseline_env(monkeypatch)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "production")
    monkeypatch.setenv("FRONTEND_ORIGINS", "https://example.com")
    with pytest.raises(ValidationError, match="SUPABASE_SERVICE_ROLE_KEY"):
        Settings(_env_file=None)


def test_service_role_required_in_preview(monkeypatch):
    """Preview tier shares the production code path for backend → Supabase
    auth, so it must also fail loudly without a service-role key."""
    _baseline_env(monkeypatch)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "preview")
    with pytest.raises(ValidationError, match="SUPABASE_SERVICE_ROLE_KEY"):
        Settings(_env_file=None)


def test_service_role_optional_in_development(monkeypatch):
    """Dev keeps service role optional — local supabase / mock setups
    don't always have it wired."""
    _baseline_env(monkeypatch)
    monkeypatch.delenv("SUPABASE_SERVICE_ROLE_KEY", raising=False)
    monkeypatch.setenv("ENVIRONMENT", "development")
    s = Settings(_env_file=None)
    assert s.SUPABASE_SERVICE_ROLE_KEY == ""
