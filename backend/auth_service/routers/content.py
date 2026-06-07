import hashlib
import hmac
import json

from fastapi import APIRouter, HTTPException, Request, Response, status
from fastapi.responses import JSONResponse

from ..services.content_locale import pick_locale_entry
from ..services.segments import apply_segments, segments_of
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
        .select("id, name, slug, is_active, preview_token, default_locale, locales")
        .eq("slug", project_slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    if not result or not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result.data


def _normalise_published(service_type: str, payload: dict) -> dict:
    """Massage published content into the shape the public website
    selectors expect.

    Currently handles `key_value`, where historic data was stored as
    `entries: [{key, value}, ...]` (array of pairs) but every consuming
    website's `keyValue(...).entries.<field>` access pattern assumes
    `entries: {key: value, ...}` (object). New saves from
    `KeyValueEditor.tsx:emit()` already write the object shape; this
    function lets old projects render correctly without a data
    migration AND keeps the new shape working unchanged.

    No-op for any other service type.
    """
    if service_type != "key_value":
        return payload
    entries = payload.get("entries")
    if isinstance(entries, list):
        flattened: dict = {}
        for item in entries:
            if not isinstance(item, dict):
                continue
            key = item.get("key")
            if not isinstance(key, str) or not key.strip():
                continue
            flattened[key.strip()] = item.get("value")
        return {**payload, "entries": flattened}
    return payload


def _content_for_locale(
    svc: dict, locale: str, default_locale: str, *, draft: bool
) -> tuple[dict | None, str | None]:
    """Return (content, updated_at) for one service in `locale`, or (None, None)
    to skip. Builds on the default-locale row and overlays the requested locale's
    translatable leaves so missing translations fall back to the default."""
    embedded = svc.get("content_entries")
    default_entry = pick_locale_entry(embedded, default_locale, default_locale)
    locale_entry = pick_locale_entry(embedded, locale, default_locale)

    def _raw(entry: dict | None) -> dict | None:
        if entry is None:
            return None
        if draft:
            d = entry.get("draft_content")
            return d if d is not None else entry.get("published_content")
        return entry.get("published_content")

    default_raw = _raw(default_entry)
    if default_raw is None:
        return None, None  # nothing published/drafted in the default → skip service

    service_type = svc["service_type_slug"]
    # Deepcopy unconditionally (JSONB content is JSON-safe) so we never alias or
    # mutate the live Supabase response dict when spreading it into content_map.
    base = json.loads(json.dumps(_normalise_published(service_type, default_raw)))
    locale_raw = _raw(locale_entry) if locale_entry is not None else None
    if locale_raw is not None and locale_entry is not default_entry:
        overlay = segments_of(service_type, _normalise_published(service_type, locale_raw))
        apply_segments(base, service_type, overlay)  # in-place; base is already a copy

    updated_at = (locale_entry or default_entry or {}).get("updated_at")
    return base, updated_at


def _build_content_map(
    services: list, locale: str, default_locale: str, *, draft: bool
) -> tuple[dict, str | None]:
    content_map: dict = {}
    last_updated: str | None = None
    for svc in services or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue
        content, updated_at = _content_for_locale(svc, locale, default_locale, draft=draft)
        if content is None:
            continue
        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at
        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **content,
        }
    return content_map, last_updated


@router.get("/{project_slug}")
async def get_project_content(project_slug: str, request: Request):
    project = _resolve_project(project_slug)

    sb = get_supabase_admin()
    services_result = (
        sb.table("project_services")
        .select(
            "service_key, label, display_order, service_type_slug, content_entries(locale, published_content, draft_content, updated_at)"
        )
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    content_map: dict = {}
    last_updated: str | None = None
    default_locale = project.get("default_locale") or "en"

    for svc in services_result.data or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue

        entry = pick_locale_entry(svc.get("content_entries"), default_locale, default_locale)
        raw_published: dict | None = entry.get("published_content") if entry else None
        # Filter: services with no published content don't appear in the public response.
        if raw_published is None:
            continue
        updated_at: str | None = entry.get("updated_at") if entry else None

        if updated_at and (last_updated is None or updated_at > last_updated):
            last_updated = updated_at

        normalised = _normalise_published(svc["service_type_slug"], raw_published)
        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **normalised,
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
            "service_key, label, display_order, service_type_slug, content_entries(locale, published_content, draft_content, updated_at)"
        )
        .eq("project_id", project["id"])
        .order("display_order")
        .execute()
    )

    content_map: dict = {}
    last_updated: str | None = None
    default_locale = project.get("default_locale") or "en"

    for svc in services_result.data or []:
        if svc["service_type_slug"] in _PRIVATE_SERVICE_TYPES:
            continue

        entry = pick_locale_entry(svc.get("content_entries"), default_locale, default_locale)
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

        normalised = _normalise_published(svc["service_type_slug"], raw)
        content_map[svc["service_key"]] = {
            "_type": svc["service_type_slug"],
            "_label": svc.get("label") or svc["service_key"],
            **normalised,
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


def _fetch_services(project_id: str):
    sb = get_supabase_admin()
    return (
        sb.table("project_services")
        .select(
            "service_key, label, display_order, service_type_slug, content_entries(locale, published_content, draft_content, updated_at)"
        )
        .eq("project_id", project_id)
        .order("display_order")
        .execute()
    )


@router.get("/{project_slug}/{locale}")
async def get_project_content_locale(project_slug: str, locale: str, request: Request):
    project = _resolve_project(project_slug)
    default_locale = project.get("default_locale") or "en"
    if locale not in (project.get("locales") or [default_locale]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locale not configured")

    services_result = _fetch_services(project["id"])
    content_map, last_updated = _build_content_map(
        services_result.data, locale, default_locale, draft=False
    )

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "locale": locale,
        "last_updated": last_updated,
        "content": content_map,
    }
    body_str = json.dumps(payload, sort_keys=True, default=str)
    etag = f'"{hashlib.sha256(body_str.encode()).hexdigest()[:16]}"'
    _cors, _cc = "Access-Control-Allow-Origin", "Cache-Control"
    if request.headers.get("If-None-Match") == etag:
        return Response(status_code=304, headers={_cc: "no-cache", "ETag": etag, _cors: "*"})
    headers = {_cc: "no-cache", "ETag": etag, _cors: "*"}
    if last_updated:
        headers["Last-Modified"] = last_updated
    return JSONResponse(content=payload, headers=headers)


@router.get("/{project_slug}/{locale}/draft")
async def get_project_draft_content_locale(project_slug: str, locale: str, request: Request):
    project = _resolve_project(project_slug)

    token_header = request.headers.get("X-CMS-Preview-Token")
    expected = project.get("preview_token")
    if not expected or not token_header or not hmac.compare_digest(token_header, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing preview token"
        )

    default_locale = project.get("default_locale") or "en"
    if locale not in (project.get("locales") or [default_locale]):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Locale not configured")

    services_result = _fetch_services(project["id"])
    content_map, last_updated = _build_content_map(
        services_result.data, locale, default_locale, draft=True
    )

    payload = {
        "project_slug": project["slug"],
        "project_name": project["name"],
        "locale": locale,
        "last_updated": last_updated,
        "content": content_map,
    }
    return JSONResponse(
        content=payload,
        headers={"Cache-Control": "no-store", "Access-Control-Allow-Origin": "*"},
    )
