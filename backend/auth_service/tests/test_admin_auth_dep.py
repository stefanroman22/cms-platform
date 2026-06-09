"""Unit tests for admin_user_via_bearer_or_sid.

Three fork points: Bearer present + valid → return user.
Bearer present + invalid → 401. No Bearer → fall through to sid path.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from auth_service.routers import deps


def _request(headers: dict | None = None, cookies: dict | None = None):
    req = MagicMock()
    req.headers = headers or {}
    req.cookies = cookies or {}
    return req


@pytest.mark.asyncio
async def test_bearer_valid_returns_userout():
    """The bearer path must return a UserOut (attribute access), NOT the raw dict
    from verify_admin_api_key — else require_project_access (user.id / user.is_admin)
    500s on every bearer call to booking-admin + workspace service endpoints."""
    from auth_service.models.schemas import UserOut

    with patch.object(
        deps,
        "verify_admin_api_key",
        return_value={"id": "u1", "email": "a@b", "is_admin": True, "is_active": True},
    ):
        user = await deps.admin_user_via_bearer_or_sid(
            _request(headers={"authorization": "Bearer cmsk_dev_xx_yy"})
        )
        assert isinstance(user, UserOut)
        assert user.id == "u1"
        assert user.is_admin is True
        # require_project_access does owner-or-admin via attribute access — must not raise.
        with patch.object(deps, "get_supabase_admin") as sb:
            sb.return_value.table.return_value.select.return_value.eq.return_value.eq.return_value.maybe_single.return_value.execute.return_value.data = {
                "user_id": "someone-else",
                "id": "p1",
            }
            project = deps.require_project_access("acme", user)
        assert project["id"] == "p1"  # admin bypasses ownership without AttributeError


@pytest.mark.asyncio
async def test_bearer_invalid_raises_401():
    with patch.object(deps, "verify_admin_api_key", return_value=None):
        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(
                _request(headers={"authorization": "Bearer cmsk_dev_xx_yy"})
            )
        assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_no_bearer_falls_through_to_sid_admin():
    fake_user = MagicMock(id="u2", is_admin=True)
    with patch.object(deps, "require_user", new=AsyncMock(return_value=fake_user)):
        user = await deps.admin_user_via_bearer_or_sid(_request(cookies={"sid": "sess123"}))
        assert user is fake_user


@pytest.mark.asyncio
async def test_no_bearer_non_admin_raises_403():
    fake_user = MagicMock(id="u3", is_admin=False)
    with patch.object(deps, "require_user", new=AsyncMock(return_value=fake_user)):
        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(_request(cookies={"sid": "sess123"}))
        assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_bearer_blocked_on_rate_limit():
    """11th attempt within 60s from the same IP must 429 before
    `verify_admin_api_key` is called."""
    from auth_service.core import bearer_limiter

    # Fresh bucket so this test isn't order-dependent.
    bearer_limiter._BEARER_BUCKET = bearer_limiter.Bucket(capacity=10, window_seconds=60)
    headers = {"authorization": "Bearer cmsk_dev_aaaaaaaaaaaaaaaa_bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"}

    req = MagicMock()
    req.headers = headers
    req.cookies = {}
    req.client = MagicMock(host="203.0.113.5")

    # Verify is patched to a fail (so we burn through the bucket
    # without succeeding). 10 fails are still allowed by the limiter,
    # 11th must hit 429.
    with patch.object(deps, "verify_admin_api_key", return_value=None):
        for _ in range(10):
            with pytest.raises(HTTPException) as exc:
                await deps.admin_user_via_bearer_or_sid(req)
            assert exc.value.status_code == 401

        with pytest.raises(HTTPException) as exc:
            await deps.admin_user_via_bearer_or_sid(req)
        assert exc.value.status_code == 429
