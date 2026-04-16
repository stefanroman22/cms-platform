from fastapi import APIRouter, HTTPException, Request, status
from typing import List

from ..models.schemas import ProjectOut, AccountOut, ProjectRequestIn
from ..services.auth_service import get_user_from_access_token
from ..services.supabase_client import get_supabase

router = APIRouter(prefix="", tags=["projects"])

ACCESS_COOKIE = "access_token"

PROJECT_TYPES = {"website", "web_app", "mobile_app", "other"}


async def _require_user(request: Request):
    token = request.cookies.get(ACCESS_COOKIE)
    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
    user = await get_user_from_access_token(token)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired token")
    return user


@router.get("/projects", response_model=List[ProjectOut])
async def list_projects(request: Request):
    user = await _require_user(request)
    sb = get_supabase()
    result = (
        sb.table("projects")
        .select("id, name, description, slug, is_active, website_url, created_at, updated_at")
        .eq("user_id", user.id)
        .eq("is_active", True)
        .order("created_at", desc=True)
        .execute()
    )
    return result.data


@router.get("/account", response_model=AccountOut)
async def get_account(request: Request):
    user = await _require_user(request)
    sb = get_supabase()
    user_result = (
        sb.table("users")
        .select("id, email, full_name, is_admin, created_at")
        .eq("id", user.id)
        .single()
        .execute()
    )
    count_result = (
        sb.table("projects")
        .select("id", count="exact")
        .eq("user_id", user.id)
        .eq("is_active", True)
        .execute()
    )
    return {
        **user_result.data,
        "projects_count": count_result.count or 0,
    }


@router.post("/project-requests", status_code=status.HTTP_201_CREATED)
async def create_project_request(body: ProjectRequestIn, request: Request):
    if body.type not in PROJECT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"type must be one of: {', '.join(PROJECT_TYPES)}",
        )
    user = await _require_user(request)
    sb = get_supabase()
    sb.table("project_requests").insert({
        "user_id": user.id,
        "name": body.name,
        "type": body.type,
        "description": body.description,
        "budget_range": body.budget_range or None,
        "timeline": body.timeline or None,
    }).execute()
    return {"success": True}
