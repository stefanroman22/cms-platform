import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ..services.supabase_client import get_supabase_admin

router = APIRouter(prefix="/content", tags=["content"])

# Service types that must NEVER appear in the public response
_PRIVATE_SERVICE_TYPES = {"email_config"}

# TS type shapes per service type slug
_TS_TYPE_MAP: dict[str, str] = {
    "text_block": '{ _type: "text_block"; _label: string; title?: string; body?: string }',
    "image": '{ _type: "image"; _label: string; url?: string; alt?: string }',
    "gallery": '{ _type: "gallery"; _label: string; items?: string[] }',
    "floor_plan": '{ _type: "floor_plan"; _label: string; url?: string; alt?: string }',
    "video": '{ _type: "video"; _label: string; url?: string; poster?: string }',
    "file_download": '{ _type: "file_download"; _label: string; url?: string; filename?: string }',
    "key_value": '{ _type: "key_value"; _label: string; entries?: Record<string, unknown> }',
    "repeater": '{ _type: "repeater"; _label: string; _schema?: Array<{ key: string; label: string; type: string }>; items?: Record<string, unknown>[] }',
}


def _resolve_project(project_slug: str) -> dict:
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("id, name, slug, is_active, preview_token")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result.data


def _resolve_content_entry(svc: dict) -> dict | None:
    """Normalises content_entries embed — supabase-py returns a dict when a
    unique constraint on the FK makes PostgREST treat it as one-to-one."""
    raw = svc.get("content_entries")
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, list):
        return raw[0] if raw else None
    return None


@router.get("/{project_slug}")
async def get_project_content(project_slug: str, request: Request):
    project = _resolve_project(project_slug)

    sb = get_supabase_admin()
    services_result = (
        sb.table("project_services")
        .select(
            "service_key, label, display_order, service_type_slug, content_entries(published_content, draft_content, updated_at)"
        )
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    content_map: dict = {}
    last_updated: str | None = None

    for svc in services_result.data or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue

        entry = _resolve_content_entry(svc)
        raw_published: dict | None = entry.get("published_content") if entry else None
        # Filter: services with no published content don't appear in the public response.
        if raw_published is None:
            continue
        updated_at: str | None = entry.get("updated_at") if entry else None

        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at

        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **raw_published,
        }

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "last_updated": last_updated,
        "content": content_map,
    }

    # ETag: stable fingerprint of the response body
    body_str = json.dumps(payload, sort_keys=True, default=str)
    etag = f'"{hashlib.sha256(body_str.encode()).hexdigest()[:16]}"'

    _cors = "Access-Control-Allow-Origin"
    _cc = "Cache-Control"

    # Conditional GET — return 304 when the client already has current content
    if request.headers.get("If-None-Match") == etag:
        return Response(
            status_code=304,
            headers={_cc: "no-cache", "ETag": etag, _cors: "*"},
        )

    headers = {
        # no-cache: always revalidate; ETag makes revalidation near-free (304)
        _cc: "no-cache",
        "ETag": etag,
        _cors: "*",
    }
    if last_updated:
        headers["Last-Modified"] = last_updated

    return JSONResponse(content=payload, headers=headers)


@router.get("/{project_slug}/draft")
async def get_project_draft_content(project_slug: str, request: Request):
    """Draft content for preview deployments. Requires X-CMS-Preview-Token header."""
    project = _resolve_project(project_slug)

    token_header = request.headers.get("X-CMS-Preview-Token")
    expected = project.get("preview_token")
    if not expected or not token_header or not hmac.compare_digest(token_header, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing preview token"
        )

    sb = get_supabase_admin()
    services_result = (
        sb.table("project_services")
        .select(
            "service_key, label, display_order, service_type_slug, content_entries(published_content, draft_content, updated_at)"
        )
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    content_map: dict = {}
    last_updated: str | None = None

    for svc in services_result.data or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue

        entry = _resolve_content_entry(svc)
        if entry is None:
            continue

        # Draft with fallback to published. Use `is not None` instead of `or`
        # so an explicitly-cleared draft ({}) renders as-is rather than falling
        # back to published content.
        draft = entry.get("draft_content")
        raw = draft if draft is not None else entry.get("published_content")
        if raw is None:
            continue

        updated_at: str | None = entry.get("updated_at")
        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at

        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **raw,
        }

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "last_updated": last_updated,
        "content": content_map,
    }

    return JSONResponse(
        content=payload,
        headers={
            "Cache-Control": "no-store",
            "Access-Control-Allow-Origin": "*",
        },
    )


@router.get("/{project_slug}/types")
async def get_project_types(project_slug: str):
    """Returns a TypeScript .d.ts interface for the project's public content shape."""
    project = _resolve_project(project_slug)

    sb = get_supabase_admin()
    services_result = (
        sb.table("project_services")
        .select("service_key, service_type_slug, label")
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    lines = [
        f"// Auto-generated types for project: {project_slug}",
        "// Do not edit — regenerate with: GET /content/{slug}/types",
        "",
        "export interface CMSContent {",
        f'  project_slug: "{project_slug}";',
        "  project_name: string;",
        "  last_updated: string | null;",
        "  content: {",
    ]

    for svc in services_result.data or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue
        ts_type = _TS_TYPE_MAP.get(svc["service_type_slug"], "Record<string, unknown>")
        lines.append(f'    {svc["service_key"]}: {ts_type};')

    lines += ["  };", "}"]

    return Response(
        content="\n".join(lines),
        media_type="text/plain",
        headers={
            "Access-Control-Allow-Origin": "*",
            "Cache-Control": "public, max-age=300",
        },
    )
