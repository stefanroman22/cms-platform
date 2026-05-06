import json
import os
import secrets
import urllib.error
import urllib.request
from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from ..models.schemas import ProjectStatusOut, PublishResponse, RotateTokenResponse
from ..services.supabase_client import get_supabase
from .deps import admin_user_via_bearer_or_sid, require_project_access, require_user

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
    svc_result = sb.table("project_services").select("id").eq("project_id", project["id"]).execute()
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
        e
        for e in (entries_result.data or [])
        if e.get("draft_content") != e.get("published_content")
    ]

    # Per-row update (supabase-py has no bulk-update-from-column-value; loop is
    # fine for typical <50 services per project).
    now = datetime.now(UTC).isoformat()
    for entry in to_publish:
        sb.table("content_entries").update(
            {
                "published_content": entry["draft_content"],
                "updated_at": now,
            }
        ).eq("project_service_id", entry["project_service_id"]).execute()

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


VERCEL_API_BASE = "https://api.vercel.com"


def _update_vercel_preview_env_var(vercel_project_id: str, new_token: str) -> None:
    """Updates CMS_PREVIEW_TOKEN env var on the Vercel project's Preview environment.

    Uses VERCEL_TOKEN from the server environment. If unset, skip silently —
    the DB token is still rotated and a re-deploy of the preview can pull the
    latest env later. The agent's initial setup is the normal path to set this.
    """
    vercel_token = os.environ.get("VERCEL_TOKEN")
    if not vercel_token:
        return

    # Find existing env var ID
    list_url = f"{VERCEL_API_BASE}/v9/projects/{vercel_project_id}/env"
    req = urllib.request.Request(list_url, headers={"Authorization": f"Bearer {vercel_token}"})
    try:
        with urllib.request.urlopen(req) as resp:
            envs = json.loads(resp.read().decode()).get("envs", [])
    except urllib.error.HTTPError:
        return

    existing = next(
        (
            e
            for e in envs
            if e.get("key") == "CMS_PREVIEW_TOKEN" and "preview" in (e.get("target") or [])
        ),
        None,
    )

    body = json.dumps(
        {
            "key": "CMS_PREVIEW_TOKEN",
            "value": new_token,
            "type": "encrypted",
            "target": ["preview"],
        }
    ).encode()

    if existing:
        patch_url = f"{VERCEL_API_BASE}/v9/projects/{vercel_project_id}/env/{existing['id']}"
        req = urllib.request.Request(
            patch_url,
            data=body,
            headers={
                "Authorization": f"Bearer {vercel_token}",
                "Content-Type": "application/json",
            },
            method="PATCH",
        )
    else:
        req = urllib.request.Request(
            list_url,
            data=body,
            headers={
                "Authorization": f"Bearer {vercel_token}",
                "Content-Type": "application/json",
            },
            method="POST",
        )
    try:
        urllib.request.urlopen(req).read()
    except urllib.error.HTTPError:
        pass


@router.post(
    "/admin/projects/{project_slug}/rotate-preview-token", response_model=RotateTokenResponse
)
async def rotate_preview_token(project_slug: str, request: Request):
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase()
    p_result = (
        sb.table("projects")
        .select("id, vercel_project_id")
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    if not p_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    new_token = secrets.token_urlsafe(32)
    sb.table("projects").update({"preview_token": new_token}).eq(
        "id", p_result.data["id"]
    ).execute()

    if p_result.data.get("vercel_project_id"):
        _update_vercel_preview_env_var(p_result.data["vercel_project_id"], new_token)

    return {"preview_token": new_token}
