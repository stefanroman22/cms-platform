from fastapi import HTTPException, Request, status

from ..models.schemas import UserOut
from ..services.admin_keys import verify_admin_api_key
from ..services.sessions import validate_session
from ..services.supabase_client import get_supabase

SESSION_COOKIE = "sid"


async def require_user(request: Request) -> UserOut:
    sid = request.cookies.get(SESSION_COOKIE)
    user = await validate_session(sid)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    return user


def require_project_access(project_slug: str, user: UserOut) -> dict:
    """Resolves project and checks ownership or admin. Returns project row."""
    sb = get_supabase()
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

    Accepts EITHER an `Authorization: Bearer cmsk_…` header (agent path)
    OR a `sid` cookie (dashboard path). Bearer wins if both are sent.
    Falls through to `require_user` for the cookie path so the existing
    session-validation logic keeps applying unchanged.
    """
    auth_header = request.headers.get("authorization", "")
    if auth_header.lower().startswith("bearer "):
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
