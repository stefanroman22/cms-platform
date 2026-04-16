from datetime import datetime, timezone
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError

from .supabase_client import get_supabase
from ..core.security import (
    create_access_token,
    create_refresh_token,
    hash_token,
    decode_access_token,
)
from ..models.schemas import UserOut

ph = PasswordHasher(
    time_cost=3,       # OWASP recommended
    memory_cost=65536, # 64 MB
    parallelism=4,
)


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_password(plain: str) -> str:
    return ph.hash(plain)


async def authenticate_user(email: str, password: str) -> Optional[dict]:
    sb = get_supabase()
    result = sb.table("users").select("*").eq("email", email).eq("is_active", True).single().execute()
    if not result.data:
        return None
    user = result.data
    if not verify_password(password, user["password_hash"]):
        return None
    return user


MAX_SESSIONS_PER_USER = 5


async def issue_tokens(user: dict, remember_me: bool) -> tuple[str, str, datetime]:
    """Returns (access_token, raw_refresh_token, refresh_expires_at)."""
    access_token = create_access_token(user["id"], user["email"], bool(user.get("is_admin", False)))
    raw_refresh, expires_at = create_refresh_token(remember_me)
    token_hash = hash_token(raw_refresh)

    sb = get_supabase()

    # Enforce session cap: revoke oldest active tokens if over the limit
    active = (
        sb.table("refresh_tokens")
        .select("id, created_at")
        .eq("user_id", user["id"])
        .eq("revoked", False)
        .order("created_at", desc=False)
        .execute()
    )
    if active.data and len(active.data) >= MAX_SESSIONS_PER_USER:
        overflow = len(active.data) - MAX_SESSIONS_PER_USER + 1
        oldest_ids = [r["id"] for r in active.data[:overflow]]
        sb.table("refresh_tokens").update({"revoked": True}).in_("id", oldest_ids).execute()

    sb.table("refresh_tokens").insert({
        "user_id": user["id"],
        "token_hash": token_hash,
        "expires_at": expires_at.isoformat(),
        "revoked": False,
        "remember_me": remember_me,
    }).execute()

    return access_token, raw_refresh, expires_at


async def refresh_access_token(raw_refresh: str) -> Optional[tuple[str, str, datetime]]:
    """Validates refresh token, rotates it, returns new (access_token, new_raw_refresh, expires_at)."""
    token_hash = hash_token(raw_refresh)
    sb = get_supabase()

    result = (
        sb.table("refresh_tokens")
        .select("*, users(*)")
        .eq("token_hash", token_hash)
        .eq("revoked", False)
        .single()
        .execute()
    )
    if not result.data:
        return None

    record = result.data
    expires_at = datetime.fromisoformat(record["expires_at"])
    if expires_at < datetime.now(timezone.utc):
        return None

    user = record["users"]
    if not user or not user.get("is_active"):
        return None

    # Rotate: revoke old token
    sb.table("refresh_tokens").update({"revoked": True}).eq("token_hash", token_hash).execute()

    # Opportunistic cleanup: delete expired/revoked rows for this user
    sb.table("refresh_tokens").delete().eq("user_id", record["user_id"]).eq("revoked", True).execute()
    sb.table("refresh_tokens").delete().eq("user_id", record["user_id"]).lt("expires_at", datetime.now(timezone.utc).isoformat()).execute()

    # Preserve the original remember_me flag stored on the token row
    remember_me = bool(record.get("remember_me", False))
    access_token, new_raw_refresh, new_expires_at = await issue_tokens(user, remember_me)
    return access_token, new_raw_refresh, new_expires_at


async def revoke_refresh_token(raw_refresh: str) -> None:
    token_hash = hash_token(raw_refresh)
    sb = get_supabase()
    sb.table("refresh_tokens").update({"revoked": True}).eq("token_hash", token_hash).execute()


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Returns True on success, False if current_password is wrong."""
    sb = get_supabase()
    result = sb.table("users").select("password_hash").eq("id", user_id).eq("is_active", True).single().execute()
    if not result.data:
        return False
    if not verify_password(current_password, result.data["password_hash"]):
        return False
    new_hash = hash_password(new_password)
    sb.table("users").update({"password_hash": new_hash}).eq("id", user_id).execute()
    return True


async def get_user_from_access_token(token: str) -> Optional[UserOut]:
    payload = decode_access_token(token)
    if not payload:
        return None
    return UserOut(
        id=payload["sub"],
        email=payload["email"],
        is_admin=bool(payload.get("is_admin", False)),
    )
