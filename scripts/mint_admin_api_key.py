"""mint_admin_api_key.py — interactive operator script.

Mints a new admin API key for an existing admin user and prints it
ONCE. Operator copies it into the agent's .env immediately. Lost = mint
a new one.

Required env (read from your shell, NOT from the script):
  SUPABASE_URL                  https://<ref>.supabase.co
  SUPABASE_SERVICE_ROLE_KEY     sb_secret_*

Run:
    python scripts/mint_admin_api_key.py
"""

from __future__ import annotations

import os
import sys
from datetime import UTC, datetime, timedelta

# Make backend modules importable.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

from auth_service.services.admin_keys import mint_admin_api_key  # noqa: E402
from auth_service.services.supabase_client import get_supabase_admin  # noqa: E402


def main() -> int:
    if not os.environ.get("SUPABASE_URL") or not os.environ.get("SUPABASE_SERVICE_ROLE_KEY"):
        print(
            "error: set SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY first.",
            file=sys.stderr,
        )
        return 1

    email = input("Admin email: ").strip().lower()
    name = input("Key name (e.g. cms-connector-agent): ").strip() or "unnamed"
    env_tier = input("Env tier [dev/prod, default dev]: ").strip() or "dev"
    if env_tier not in {"dev", "prod"}:
        print(f"error: env tier must be dev or prod, got {env_tier!r}", file=sys.stderr)
        return 1
    expiry_choice = input("Expires in days [blank=never, 90, 180, 365]: ").strip()
    expires_at = None
    if expiry_choice:
        try:
            days = int(expiry_choice)
        except ValueError:
            print("error: expiry must be a number of days", file=sys.stderr)
            return 1
        expires_at = (datetime.now(UTC) + timedelta(days=days)).isoformat()

    sb = get_supabase_admin()
    res = (
        sb.table("users")
        .select("id, email, is_admin")
        .eq("email", email)
        .eq("is_admin", True)
        .maybe_single()
        .execute()
    )
    user = res.data if res else None
    if not user:
        print(f"error: no admin user with email {email!r}", file=sys.stderr)
        return 1

    plain, row_id = mint_admin_api_key(
        user_id=user["id"],
        name=name,
        env=env_tier,
        expires_at=expires_at,
    )

    print()
    print("=" * 64)
    print("  COPY THIS KEY NOW — it will not be shown again:")
    print()
    print(f"    {plain}")
    print()
    print(f"  Owner: {email}    Name: {name}    Row id: {row_id}")
    if expires_at:
        print(f"  Expires: {expires_at}")
    print("=" * 64)
    print()
    print("Paste into agents/CMS Connector - Website/.env as:")
    print(f"    CMS_ADMIN_API_KEY={plain}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
