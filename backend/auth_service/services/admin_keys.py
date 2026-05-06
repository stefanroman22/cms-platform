"""Admin API key minting and verification.

Key format: cmsk_<env>_<lookup>_<secret>
- env: "dev" or "prod" (informational)
- lookup: 16 base64url chars, stored as key_prefix for fast row lookup
- secret: 32 base64url chars, argon2-hashed at rest

The verifier parses the lookup half, fetches the single matching row,
and argon2-verifies the secret half against key_hash. Constant cost
per request regardless of how many keys exist.
"""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

from .supabase_client import get_supabase_admin

KEY_PREFIX_LEN = 16
SECRET_LEN_TARGET = 32

_ph = PasswordHasher(time_cost=3, memory_cost=65536, parallelism=4)


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def mint_admin_api_key(
    *,
    user_id: str,
    name: str,
    env: Literal["dev", "prod"] = "dev",
    expires_at: str | None = None,
) -> tuple[str, str]:
    """Generates a new key, stores its hash, returns (plain_key, row_id).

    The plain key is the only thing that can be used to authenticate;
    callers must hand it to the operator immediately and never log it.
    """
    # token_hex emits 0-9a-f only — never `_`, so the cmsk_<env>_<lookup>_<secret>
    # split-on-underscore parser never desyncs. 8 bytes = 16 hex chars (lookup),
    # 16 bytes = 32 hex chars (secret) — same lengths as the previous attempt.
    lookup = secrets.token_hex(KEY_PREFIX_LEN // 2)
    secret = secrets.token_hex(SECRET_LEN_TARGET // 2)
    plain = f"cmsk_{env}_{lookup}_{secret}"
    row = (
        get_supabase_admin()
        .table("admin_api_keys")
        .insert(
            {
                "user_id": user_id,
                "key_prefix": lookup,
                "key_hash": _ph.hash(secret),
                "name": name,
                "expires_at": expires_at,
            }
        )
        .execute()
    )
    return plain, row.data[0]["id"] if row.data else ""


def verify_admin_api_key(plain_key: str) -> dict | None:
    """Returns the user dict if `plain_key` matches an active, non-expired,
    non-revoked admin key. Updates last_used_at on success."""
    parts = plain_key.split("_") if plain_key else []
    if len(parts) != 4 or parts[0] != "cmsk" or parts[1] not in {"dev", "prod"}:
        return None
    lookup, secret = parts[2], parts[3]
    if len(lookup) != KEY_PREFIX_LEN:
        return None

    sb = get_supabase_admin()
    res = (
        sb.table("admin_api_keys")
        .select("id, user_id, key_hash, expires_at, scopes, " "users(email, is_admin, is_active)")
        .eq("key_prefix", lookup)
        .is_("revoked_at", "null")
        .maybe_single()
        .execute()
    )
    row = res.data if res else None
    if not row:
        return None

    if row.get("expires_at") and row["expires_at"] <= _now_iso():
        return None

    try:
        _ph.verify(row["key_hash"], secret)
    except VerifyMismatchError:
        return None

    u = row.get("users") or {}
    if not (u.get("is_admin") and u.get("is_active")):
        return None

    sb.table("admin_api_keys").update({"last_used_at": _now_iso()}).eq("id", row["id"]).execute()
    return {
        "id": row["user_id"],
        "email": u["email"],
        "is_admin": u["is_admin"],
        "is_active": u["is_active"],
    }
