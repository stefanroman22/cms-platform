from fastapi import HTTPException, Request, status

from ..models.schemas import UserOut
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
