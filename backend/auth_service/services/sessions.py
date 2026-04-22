from datetime import datetime, timedelta, timezone
from typing import Optional

from .supabase_client import get_supabase
from ..core.security import generate_session_id, hash_token
from ..models.schemas import UserOut

DEFAULT_DAYS = 30
REMEMBER_ME_DAYS = 60
RENEWAL_WINDOW = timedelta(minutes=5)
MAX_SESSIONS_PER_USER = 5


async def create_session(
    user: dict,
    remember_me: bool,
    user_agent: Optional[str] = None,
    ip: Optional[str] = None,
) -> tuple[str, datetime]:
    """Issues a fresh session. Returns (raw_sid, expires_at).

    Caller writes the `sid` cookie with raw_sid; only the hash lives in DB.
    """
    raw_sid = generate_session_id()
    token_hash = hash_token(raw_sid)
    days = REMEMBER_ME_DAYS if remember_me else DEFAULT_DAYS
    now = datetime.now(timezone.utc)
    expires_at = now + timedelta(days=days)

    sb = get_supabase()

    # Enforce session cap: revoke oldest if over limit
    active = (
        sb.table("sessions")
        .select("id, created_at")
        .eq("user_id", user["id"])
        .eq("revoked", False)
        .order("created_at", desc=False)
        .execute()
    )
    if active.data and len(active.data) >= MAX_SESSIONS_PER_USER:
        overflow = len(active.data) - MAX_SESSIONS_PER_USER + 1
        oldest_ids = [r["id"] for r in active.data[:overflow]]
        sb.table("sessions").update({"revoked": True}).in_("id", oldest_ids).execute()

    sb.table("sessions").insert({
        "user_id": user["id"],
        "token_hash": token_hash,
        "expires_at": expires_at.isoformat(),
        "revoked": False,
        "remember_me": remember_me,
        "last_used_at": now.isoformat(),
        "user_agent": user_agent,
        "ip_address": ip,
    }).execute()

    return raw_sid, expires_at


async def validate_session(raw_sid: Optional[str]) -> Optional[UserOut]:
    """Returns the user for a valid sid, or None. Slides expires_at when
    remaining lifetime falls below (full_lifetime - RENEWAL_WINDOW).
    """
    if not raw_sid:
        return None
    token_hash = hash_token(raw_sid)
    sb = get_supabase()
    result = (
        sb.table("sessions")
        .select("id, expires_at, remember_me, users(id, email, full_name, is_admin, is_active)")
        .eq("token_hash", token_hash)
        .eq("revoked", False)
        .maybe_single()
        .execute()
    )
    # maybe_single() returns APIResponse(data=None) on 0 rows rather than
    # raising PGRST116, which is the graceful behaviour we want here.
    if result is None or not getattr(result, "data", None):
        return None
    row = result.data
    now = datetime.now(timezone.utc)
    expires_at = datetime.fromisoformat(row["expires_at"])
    if expires_at < now:
        return None

    user = row.get("users")
    if not user or not user.get("is_active"):
        return None

    remaining = expires_at - now
    full_lifetime = timedelta(days=REMEMBER_ME_DAYS if row.get("remember_me") else DEFAULT_DAYS)
    if remaining < full_lifetime - RENEWAL_WINDOW:
        new_expires = now + full_lifetime
        sb.table("sessions").update({
            "expires_at": new_expires.isoformat(),
            "last_used_at": now.isoformat(),
        }).eq("id", row["id"]).execute()

    return UserOut(
        id=user["id"],
        email=user["email"],
        full_name=user.get("full_name"),
        is_admin=bool(user.get("is_admin", False)),
    )


async def revoke_session(raw_sid: str) -> None:
    """Marks the single session for this sid as revoked. No-op on unknown sid."""
    if not raw_sid:
        return
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("token_hash", hash_token(raw_sid)).execute()


async def revoke_all_for_user(user_id: str) -> None:
    """Marks every active session for this user as revoked. Used on password change."""
    sb = get_supabase()
    sb.table("sessions").update({"revoked": True}).eq("user_id", user_id).eq("revoked", False).execute()
