from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .supabase_client import get_supabase

ph = PasswordHasher(
    time_cost=3,  # OWASP recommended
    memory_cost=65536,  # 64 MB
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


async def authenticate_user(email: str, password: str) -> dict | None:
    sb = get_supabase()
    # maybe_single() returns None on 0 rows (vs single() which raises PGRST116
    # → 500). Wrong email must yield 401, not 500.
    result = (
        sb.table("users")
        .select("*")
        .eq("email", email)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        return None
    user = result.data
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Returns True on success, False if current_password is wrong."""
    sb = get_supabase()
    result = (
        sb.table("users")
        .select("password_hash")
        .eq("id", user_id)
        .eq("is_active", True)
        .single()
        .execute()
    )
    if not result.data:
        return False
    if not verify_password(current_password, result.data["password_hash"]):
        return False
    new_hash = hash_password(new_password)
    sb.table("users").update({"password_hash": new_hash}).eq("id", user_id).execute()
    return True
