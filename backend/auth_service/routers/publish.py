import logging
import secrets
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import ProjectStatusOut, PublishResponse, RotateTokenResponse
from ..services.storage_gc import prune_unreferenced_uploads
from ..services.supabase_client import get_supabase_admin
from .deps import admin_user_via_bearer_or_sid, require_project_access, require_user

logger = logging.getLogger(__name__)
router = APIRouter(tags=["publish"])


@router.post("/projects/{project_slug}/publish", response_model=PublishResponse)
async def publish_project(project_slug: str, request: Request):
    """Atomically promotes draft_content → published_content for every service
    in the project where they differ. Bumps projects.last_published_at.
    """
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()

    # Resolve service IDs for this project
    svc_result = sb.table("project_services").select("id").eq("project_id", project["id"]).execute()
    svc_ids = [s["id"] for s in (svc_result.data or [])]
    if not svc_ids:
        return {"published_count": 0, "last_published_at": None}

    # Identify entries that need publishing (draft differs from published).
    # supabase-py doesn't support IS DISTINCT FROM, so we fetch candidates and
    # compare in Python.
    entries_result = (
        sb.table("content_entries")
        .select("id, project_service_id, locale, draft_content, published_content")
        .in_("project_service_id", svc_ids)
        .execute()
    )

    to_publish = [
        e
        for e in (entries_result.data or [])
        if e.get("draft_content") != e.get("published_content")
    ]

    # Per-row update keyed on the row id — never on project_service_id, which
    # would overwrite every locale of the service with one locale's draft.
    now = datetime.now(UTC).isoformat()
    for entry in to_publish:
        sb.table("content_entries").update(
            {
                "published_content": entry["draft_content"],
                "updated_at": now,
            }
        ).eq("id", entry["id"]).execute()

    # Bump project timestamp (always — even on zero-publish, this is a no-op
    # from the user's perspective but records the publish action).
    sb.table("projects").update({"last_published_at": now}).eq("id", project["id"]).execute()

    # After a publish draft == published, so every file the content still uses is in the drafts.
    # Best-effort: a storage error must never fail the publish.
    try:
        prune_unreferenced_uploads(
            sb, project_slug, [e.get("draft_content") for e in (entries_result.data or [])]
        )
    except Exception:  # noqa: BLE001
        logger.warning("storage gc failed for %s", project_slug, exc_info=True)

    return {"published_count": len(to_publish), "last_published_at": now}


@router.get("/projects/{project_slug}/status", response_model=ProjectStatusOut)
async def project_status(project_slug: str, request: Request):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()

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
    svc_result = sb.table("project_services").select("id").eq("project_id", project["id"]).execute()
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
            1
            for e in (entries_result.data or [])
            if e.get("draft_content") != e.get("published_content")
        )

    return {
        "unpublished_count": unpublished_count,
        "last_published_at": p_data.get("last_published_at"),
        "preview_url": p_data.get("preview_url"),
        "production_url": p_data.get("production_url"),
    }


@router.post(
    "/admin/projects/{project_slug}/rotate-preview-token", response_model=RotateTokenResponse
)
async def rotate_preview_token(project_slug: str, request: Request):
    """Writes a new draft-preview token to the project row and returns it.
    It does not touch Vercel: whoever calls this (the CMS Connector agent)
    sets the returned token as the client site's CMS_PREVIEW_TOKEN, so the
    backend never needs a Vercel token of its own."""
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    p_result = sb.table("projects").select("id").eq("slug", project_slug).single().execute()
    if not p_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    new_token = secrets.token_urlsafe(32)
    sb.table("projects").update({"preview_token": new_token}).eq(
        "id", p_result.data["id"]
    ).execute()

    return {"preview_token": new_token}
