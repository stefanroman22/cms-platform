from fastapi import HTTPException, Request, status

from ..core.bearer_limiter import check_bearer_attempt
from ..core.limiter import client_ip
from ..models.schemas import UserOut
from ..services.admin_keys import verify_admin_api_key
from ..services.sessions import validate_session
from ..services.supabase_client import get_supabase_admin

SESSION_COOKIE = "sid"


async def require_user(request: Request) -> UserOut:
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_project_access(project_slug: str, user: UserOut) -> dict:
    """Resolves project and checks ownership or admin. Returns project row."""
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("id, name, slug, user_id, is_active")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    project = result.data
    if project["user_id"] != user.id and not user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied")
    return project


async def admin_user_via_bearer_or_sid(request: Request):
    """Auth dep used by every admin route.

    Bearer path is rate-limited (BE-011): 10 attempts/min/IP, applied
    BEFORE verify_admin_api_key so a brute-forcer can't bypass via raw
    throughput. Cookie path is unchanged — session validation is
    already cheap and hardening lives at /auth/login (BE-002).
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
        ip = client_ip(request)
        if not check_bearer_attempt(ip):
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Too many admin auth attempts; slow down.",
            )
        plain = auth_header.split(" ", 1)[1].strip()
        user = verify_admin_api_key(plain)
        if user:
            return user
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or revoked admin API key",
        )
    user = await require_user(request)
    is_admin = getattr(user, "is_admin", None)
    if is_admin is None and isinstance(user, dict):
        is_admin = user.get("is_admin")
    if not is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Admin access required",
        )
    return user
