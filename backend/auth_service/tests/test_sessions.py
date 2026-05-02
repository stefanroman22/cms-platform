from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock

import pytest

SAMPLE_USER = {
    "id": "user-1",
    "email": "u@example.com",
    "is_admin": False,
    "is_active": True,
    "full_name": "Test User",
}


@pytest.fixture
def sessions_module(mock_supabase):
    """Import sessions lazily so the mock patch targets land first."""
    from auth_service.services import sessions as mod

    return mod


async def test_create_session_stores_hashed_token_only(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])  # no active sessions
    raw_sid, expires_at = await sessions_module.create_session(SAMPLE_USER, remember_me=False)

    assert len(raw_sid) >= 32
    # Verify insert payload stored hash, not raw token
    insert_payload = mock_supabase.insert.call_args_list[0].args[0]
    assert insert_payload["token_hash"] != raw_sid
    assert len(insert_payload["token_hash"]) == 64  # sha256 hex


async def test_create_session_caps_at_5_revokes_oldest(mock_supabase, sessions_module):
    # 5 existing active sessions - next login must revoke oldest
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": f"s{i}", "created_at": f"2026-01-0{i+1}"} for i in range(5)]),
        MagicMock(data=[]),  # revoke UPDATE
        MagicMock(data=[{"id": "new"}]),  # insert
    ]
    await sessions_module.create_session(SAMPLE_USER, remember_me=False)

    update_calls = [
        c
        for c in mock_supabase.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and c.args[0].get("revoked") is True
    ]
    assert any(update_calls), "Expected a revoke UPDATE"


async def test_validate_session_returns_user_when_valid(mock_supabase, sessions_module):
    now = datetime.now(UTC)
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "s1",
            "token_hash": "abc",
            "expires_at": (now + timedelta(days=29)).isoformat(),
            "remember_me": False,
            "users": SAMPLE_USER,
        }
    )
    user = await sessions_module.validate_session("some-raw-sid")
    assert user is not None
    assert user.id == "user-1"


async def test_validate_session_returns_none_when_revoked(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=None)
    user = await sessions_module.validate_session("some-raw-sid")
    assert user is None


async def test_validate_session_returns_none_when_expired(mock_supabase, sessions_module):
    past = datetime.now(UTC) - timedelta(minutes=1)
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "s1",
            "expires_at": past.isoformat(),
            "remember_me": False,
            "users": SAMPLE_USER,
        }
    )
    user = await sessions_module.validate_session("raw")
    assert user is None


async def test_validate_session_slides_expiry_when_threshold_passed(mock_supabase, sessions_module):
    now = datetime.now(UTC)
    # Session has only 1 day remaining of a 30-day lifetime → threshold passed
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "s1",
            "expires_at": (now + timedelta(days=1)).isoformat(),
            "remember_me": False,
            "users": SAMPLE_USER,
        }
    )
    user = await sessions_module.validate_session("raw")
    assert user is not None

    update_calls = [
        c
        for c in mock_supabase.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and "expires_at" in c.args[0]
    ]
    assert len(update_calls) >= 1, "Expected a sliding expiry UPDATE"


async def test_validate_session_skips_db_update_when_throttled(mock_supabase, sessions_module):
    now = datetime.now(UTC)
    # Full lifetime remaining → no update
    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "s1",
            "expires_at": (now + timedelta(days=30)).isoformat(),
            "remember_me": False,
            "users": SAMPLE_USER,
        }
    )
    await sessions_module.validate_session("raw")
    update_calls = [
        c
        for c in mock_supabase.update.call_args_list
        if c.args and isinstance(c.args[0], dict) and "expires_at" in c.args[0]
    ]
    assert len(update_calls) == 0, "Should NOT bump expires_at within the renewal window"


async def test_validate_session_returns_none_on_unknown_hash(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=None)
    user = await sessions_module.validate_session("nonexistent")
    assert user is None


async def test_validate_session_returns_none_on_empty_input(mock_supabase, sessions_module):
    user = await sessions_module.validate_session("")
    assert user is None
    user = await sessions_module.validate_session(None)
    assert user is None


async def test_revoke_session_sets_revoked_true(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[{"id": "s1"}])
    await sessions_module.revoke_session("raw")
    update_payloads = [
        c.args[0]
        for c in mock_supabase.update.call_args_list
        if c.args and isinstance(c.args[0], dict)
    ]
    assert any(p.get("revoked") is True for p in update_payloads)


async def test_revoke_all_for_user_kills_every_active_session(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    await sessions_module.revoke_all_for_user("user-1")
    update_payloads = [
        c.args[0]
        for c in mock_supabase.update.call_args_list
        if c.args and isinstance(c.args[0], dict)
    ]
    assert any(p.get("revoked") is True for p in update_payloads)


async def test_remember_me_sets_60_day_lifetime(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    _, expires = await sessions_module.create_session(SAMPLE_USER, remember_me=True)
    expected_min = datetime.now(UTC) + timedelta(days=59)
    assert expires > expected_min


async def test_default_sets_30_day_lifetime(mock_supabase, sessions_module):
    mock_supabase.execute.return_value = MagicMock(data=[])
    _, expires = await sessions_module.create_session(SAMPLE_USER, remember_me=False)
    expected_min = datetime.now(UTC) + timedelta(days=29)
    expected_max = datetime.now(UTC) + timedelta(days=31)
    assert expected_min < expires < expected_max
