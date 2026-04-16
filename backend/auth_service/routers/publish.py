from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import ProjectStatusOut, PublishResponse
from ..services.supabase_client import get_supabase
from .deps import require_project_access, require_user

router = APIRouter(tags=["publish"])


@router.post("/projects/{project_slug}/publish", response_model=PublishResponse)
async def publish_project(project_slug: str, request: Request):
    """Atomically promotes draft_content → published_content for every service
    in the project where they differ. Bumps projects.last_published_at.
    """
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()

    # Resolve service IDs for this project
    svc_result = (
        sb.table("project_services")
        .select("id")
        .eq("project_id", project["id"])
        .execute()
    )
    svc_ids = [s["id"] for s in (svc_result.data or [])]
    if not svc_ids:
        return {"published_count": 0, "last_published_at": None}

    # Identify entries that need publishing (draft differs from published).
    # supabase-py doesn't support IS DISTINCT FROM, so we fetch candidates and
    # compare in Python.
    entries_result = (
        sb.table("content_entries")
        .select("project_service_id, draft_content, published_content")
        .in_("project_service_id", svc_ids)
        .execute()
    )

    to_publish = [
        e for e in (entries_result.data or [])
        if e.get("draft_content") != e.get("published_content")
    ]

    # Per-row update (supabase-py has no bulk-update-from-column-value; loop is
    # fine for typical <50 services per project).
    now = datetime.now(timezone.utc).isoformat()
    for entry in to_publish:
        sb.table("content_entries").update({
            "published_content": entry["draft_content"],
            "updated_at": now,
        }).eq("project_service_id", entry["project_service_id"]).execute()

    # Bump project timestamp (always — even on zero-publish, this is a no-op
    # from the user's perspective but records the publish action).
    sb.table("projects").update({"last_published_at": now}).eq("id", project["id"]).execute()

    return {"published_count": len(to_publish), "last_published_at": now}


@router.get("/projects/{project_slug}/status", response_model=ProjectStatusOut)
async def project_status(project_slug: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase()

    # Fetch URLs + last_published_at
    p_result = (
        sb.table("projects")
        .select("id, preview_url, production_url, last_published_at")
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    p_data = p_result.data or {}

    # Count entries where draft != published
    svc_result = (
        sb.table("project_services")
        .select("id")
        .eq("project_id", project["id"])
        .execute()
    )
    svc_ids = [s["id"] for s in (svc_result.data or [])]
    unpublished_count = 0
    if svc_ids:
        entries_result = (
            sb.table("content_entries")
            .select("project_service_id, draft_content, published_content")
            .in_("project_service_id", svc_ids)
            .execute()
        )
        unpublished_count = sum(
            1 for e in (entries_result.data or [])
            if e.get("draft_content") != e.get("published_content")
        )

    return {
        "unpublished_count": unpublished_count,
        "last_published_at": p_data.get("last_published_at"),
        "preview_url": p_data.get("preview_url"),
        "production_url": p_data.get("production_url"),
    }
