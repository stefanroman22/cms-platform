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
async def test_bearer_valid_returns_user():
    with patch.object(
        deps,
        "verify_admin_api_key",
        return_value={"id": "u1", "email": "a@b", "is_admin": True, "is_active": True},
    ):
        user = await deps.admin_user_via_bearer_or_sid(
            _request(headers={"authorization": "Bearer cmsk_dev_xx_yy"})
        )
        assert user["id"] == "u1"


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
