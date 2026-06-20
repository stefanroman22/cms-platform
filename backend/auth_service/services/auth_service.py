import functools

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from .supabase_client import get_supabase_admin

ph = PasswordHasher(
    time_cost=3,  # OWASP recommended
    memory_cost=65536,  # 64 MB
    parallelism=4,
)


# Dummy hash used to equalise timing on the missing-email path. Without this, an
# attacker can enumerate accounts: a wrong email returns in ~5 ms (DB round-trip
# only), a wrong password returns in ~250 ms (DB + argon2 verify). Running a verify
# against this dummy on the miss path makes both paths take the same wall-clock time.
# Computed LAZILY (not at import) so the ~150 ms argon2 hash stays off the serverless
# cold-start critical path; the first missing-email login pays it once, then it's
# cached for the life of the worker.
@functools.cache
def _timing_dummy_hash() -> str:
    return ph.hash("timing-equaliser-dummy-password-not-real-anywhere")


def verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def hash_password(plain: str) -> str:
    return ph.hash(plain)


async def authenticate_user(email: str, password: str) -> dict | None:
    sb = get_supabase_admin()
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
        # Burn the same argon2 budget as a real verify so a missing email
        # is indistinguishable from a wrong password by timing alone.
        verify_password(password, _timing_dummy_hash())
        return None
    user = result.data
    if not verify_password(password, user["password_hash"]):
        return None
    return user


async def change_user_password(user_id: str, current_password: str, new_password: str) -> bool:
    """Returns True on success, False if current_password is wrong."""
    sb = get_supabase_admin()
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
