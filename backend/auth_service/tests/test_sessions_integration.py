"""Real-DB integration tests for the sessions module.

Gated by env var CMS_RUN_DB_TESTS=1 so normal test runs skip them.

Each test creates a disposable test user with a recognizable email prefix
and cleans up after itself in a teardown fixture.
"""
import os
import uuid
from datetime import datetime, timedelta, timezone

import pytest

skip_if_no_db = pytest.mark.skipif(
    os.environ.get("CMS_RUN_DB_TESTS") != "1",
    reason="Set CMS_RUN_DB_TESTS=1 to run real-DB tests",
)


@pytest.fixture
def test_user():
    """Creates and tears down a disposable test user."""
    from auth_service.services.supabase_client import get_supabase_admin
    from auth_service.services.auth_service import hash_password

    sb = get_supabase_admin()
    email = f"test_sessions_{uuid.uuid4().hex[:8]}@internal.test"
    user_row = {
        "email": email,
        "password_hash": hash_password("test-pw-12345"),
        "full_name": "Session Test",
        "is_admin": False,
        "is_active": True,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    insert_res = sb.table("users").insert(user_row).execute()
    user = insert_res.data[0]

    yield user

    # Cleanup: delete sessions first (FK), then the user
    sb.table("sessions").delete().eq("user_id", user["id"]).execute()
    sb.table("users").delete().eq("id", user["id"]).execute()


@skip_if_no_db
async def test_full_login_logout_cycle_against_real_db(test_user):
    from auth_service.services.sessions import create_session, validate_session, revoke_session
    raw_sid, _ = await create_session(test_user, remember_me=False)

    user = await validate_session(raw_sid)
    assert user is not None
    assert user.email == test_user["email"]

    await revoke_session(raw_sid)

    user = await validate_session(raw_sid)
    assert user is None


@skip_if_no_db
async def test_session_sliding_expiry_persists_in_db(test_user):
    """Manually shrink the expiry, then validate — expect DB value to bump."""
    from auth_service.services.sessions import create_session, validate_session
    from auth_service.services.supabase_client import get_supabase_admin
    from auth_service.core.security import hash_token

    raw_sid, _ = await create_session(test_user, remember_me=False)
    sb = get_supabase_admin()
    # Force expiry to ~1 day from now (below the 5-min threshold from full 30-day lifetime)
    short_expiry = datetime.now(timezone.utc) + timedelta(days=1)
    sb.table("sessions").update(
        {"expires_at": short_expiry.isoformat()}
    ).eq("token_hash", hash_token(raw_sid)).execute()

    # Validate — should bump expiry to ~30 days from now
    await validate_session(raw_sid)

    # Read back
    row = (
        sb.table("sessions")
        .select("expires_at")
        .eq("token_hash", hash_token(raw_sid))
        .single()
        .execute()
        .data
    )
    expires_at = datetime.fromisoformat(row["expires_at"])
    assert expires_at > datetime.now(timezone.utc) + timedelta(days=29)


@skip_if_no_db
async def test_password_change_kills_sessions_from_other_devices(test_user):
    from auth_service.services.sessions import create_session, validate_session, revoke_all_for_user

    sids = []
    for _ in range(3):
        raw, _ = await create_session(test_user, remember_me=False)
        sids.append(raw)

    for s in sids:
        assert await validate_session(s) is not None

    await revoke_all_for_user(test_user["id"])

    for s in sids:
        assert await validate_session(s) is None


@skip_if_no_db
async def test_create_session_caps_at_5(test_user):
    """Creating 6 sessions should revoke the oldest, leaving 5 active."""
    from auth_service.services.sessions import create_session, validate_session

    sids = []
    for _ in range(6):
        raw, _ = await create_session(test_user, remember_me=False)
        sids.append(raw)

    # Oldest should be revoked
    assert await validate_session(sids[0]) is None
    # Remaining 5 should be valid
    for s in sids[1:]:
        assert await validate_session(s) is not None
