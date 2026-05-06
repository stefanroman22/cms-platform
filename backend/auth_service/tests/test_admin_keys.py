"""Unit tests for admin_keys service.

Mocked Supabase client; no network. Verifies the parse-then-argon2
flow plus the negative paths (expired, revoked, wrong secret, malformed,
inactive user).
"""

from unittest.mock import MagicMock, patch

import pytest
from argon2 import PasswordHasher

from auth_service.services import admin_keys

ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def _row(*, key_prefix, key_hash, expires_at=None, revoked_at=None, is_admin=True, is_active=True):
    return {
        "id": "row-1",
        "user_id": "user-1",
        "key_prefix": key_prefix,
        "key_hash": key_hash,
        "expires_at": expires_at,
        "revoked_at": revoked_at,
        "scopes": ["agent"],
        "users": {
            "email": "admin@example.com",
            "is_admin": is_admin,
            "is_active": is_active,
        },
    }


@pytest.fixture
def mock_admin_sb():
    """Patches get_supabase_admin to return a chainable mock."""
    with patch.object(admin_keys, "get_supabase_admin") as factory:
        sb = MagicMock()
        for m in ["table", "select", "eq", "is_", "maybe_single", "update", "insert"]:
            getattr(sb, m).return_value = sb
        factory.return_value = sb
        yield sb


def test_returns_user_for_valid_key(mock_admin_sb):
    secret = "z" * 32
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash(secret))
    mock_admin_sb.execute.return_value = MagicMock(data=row)

    user = admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{secret}")
    assert user is not None
    assert user["id"] == "user-1"
    assert user["email"] == "admin@example.com"


def test_returns_none_for_unknown_lookup_prefix(mock_admin_sb):
    mock_admin_sb.execute.return_value = MagicMock(data=None)
    assert (
        admin_keys.verify_admin_api_key(
            "cmsk_dev_aaaaaaaaaaaaaaaa_zzzzzzzzzzzzzzzzzzzzzzzzzzzzzzzz"
        )
        is None
    )


def test_returns_none_for_wrong_secret(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("correct" * 5))
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key("cmsk_dev_abcdefghijklmnop_" + "wrong" * 7) is None


def test_returns_none_for_expired_key(mock_admin_sb):
    row = _row(
        key_prefix="abcdefghijklmnop",
        key_hash=ph.hash("z" * 32),
        expires_at="2020-01-01T00:00:00+00:00",
    )
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_inactive_admin(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("z" * 32), is_active=False)
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_non_admin(mock_admin_sb):
    row = _row(key_prefix="abcdefghijklmnop", key_hash=ph.hash("z" * 32), is_admin=False)
    mock_admin_sb.execute.return_value = MagicMock(data=row)
    assert admin_keys.verify_admin_api_key(f"cmsk_dev_abcdefghijklmnop_{'z' * 32}") is None


def test_returns_none_for_malformed_key(mock_admin_sb):
    for bad in ["", "cmsk_only_three_parts", "notcmsk_dev_aaa_bbb", "cmsk_unknown_aaa_bbb"]:
        assert admin_keys.verify_admin_api_key(bad) is None
    mock_admin_sb.execute.assert_not_called()


def test_mint_returns_plain_key_with_correct_format(mock_admin_sb):
    mock_admin_sb.execute.return_value = MagicMock(data=[{"id": "row-2"}])
    plain, row_id = admin_keys.mint_admin_api_key(
        user_id="user-1",
        name="agent",
        env="dev",
        expires_at=None,
    )
    assert plain.startswith("cmsk_dev_")
    parts = plain.split("_")
    assert len(parts) == 4
    assert len(parts[2]) == 16  # lookup
    assert len(parts[3]) >= 32  # secret
    assert row_id == "row-2"
