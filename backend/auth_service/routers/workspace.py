import logging
import secrets
import string
import uuid
from datetime import UTC, datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, Request, UploadFile, status

from ..core.limiter import limiter
from ..models.schemas import (
    AdminProjectCreateIn,
    AdminProjectDetailOut,
    AdminProjectOut,
    AdminProjectPatchIn,
    ContentSaveRequest,
    CreateClientOut,
    CreateClientRequest,
    ProjectLocalesIn,
    ProjectLocalesOut,
    ProjectSettingsIn,
    ProjectSettingsOut,
    ProjectTransferIn,
    ServiceCreateRequest,
    ServiceDetailOut,
    ServiceOut,
    ServiceTypeOut,
    UserAdminOut,
    WelcomeEmailIn,
)
from ..services.auth_service import hash_password
from ..services.content_locale import pick_locale_entry
from ..services.segments import segments_of, src_hash
from ..services.supabase_client import get_supabase_admin
from ..services.test_data import is_test_email, is_test_slug
from ..services.welcome_email import send_welcome_email
from ..translation import get_provider
from ..translation.sync import sync_locale_draft
from .deps import (
    admin_user_via_bearer_or_sid,
    require_project_access,
    require_user,
    user_via_bearer_or_session,
)

logger = logging.getLogger(__name__)

STORAGE_BUCKET = "cms-files"
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Which MIME prefix is allowed per service type. None = any type accepted.
_ALLOWED_MIME: dict[str, str | None] = {
    "image": "image/",
    "floor_plan": "image/",
    "gallery": "image/",
    "video": "video/",
    "file_download": None,
}

# Explicit deny — INFRA-004. Even though the type prefix matches
# (image/* for SVG), the file is XML and can carry inline <script>,
# making any public-URL render a stored-XSS sink. Reject at upload.
# If a client genuinely needs SVG support, configure the bucket to
# serve it with `Content-Disposition: attachment` AND a CSP that
# blocks scripts on the bucket origin first.
_DENIED_MIME: frozenset[str] = frozenset(
    {
        "image/svg+xml",
        "text/html",
        "application/xhtml+xml",
        "application/x-shockwave-flash",
    }
)

# Fallback extensions when the uploaded filename has none.
# Note: no entry for image/svg+xml — it is denied at the MIME check
# above before this map is consulted.
_MIME_TO_EXT: dict[str, str] = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/gif": ".gif",
    "image/webp": ".webp",
    "video/mp4": ".mp4",
    "video/webm": ".webm",
    "application/pdf": ".pdf",
}

router = APIRouter(tags=["workspace"])

# ── Auth helpers ─────────────────────────────────────────────────────────────


def _translation_status(
    service_type: str, embedded, loc: str, default_locale: str
) -> dict[str, str] | None:
    """Per-leaf translation status for a NON-default locale: 'auto' (machine-managed),
    'manual' (human override, current), or 'stale' (override whose source changed).
    Returns None for the default locale (it is the source)."""
    if loc == default_locale:
        return None
    default_entry = pick_locale_entry(embedded, default_locale, default_locale) or {}
    loc_entry = pick_locale_entry(embedded, loc, default_locale) or {}
    default_content = default_entry.get("draft_content")
    if default_content is None:
        default_content = default_entry.get("published_content") or {}
    meta = loc_entry.get("translation_meta") or {}
    src_segs = segments_of(service_type, default_content)
    status: dict[str, str] = {}
    for path, source_text in src_segs.items():
        if path in meta:
            status[path] = (
                "stale" if meta[path].get("src_hash") != src_hash(source_text) else "manual"
            )
        else:
            status[path] = "auto"
    return status


def _flatten_service(svc: dict, locale: str, default_locale: str) -> dict:
    """Extracts nested service_types + the per-locale content_entries row into a
    flat dict for the dashboard.

    `content` is the draft for the chosen locale (falling back to published, then
    to the default-locale row). Uses `is not None` (not `or`) so an explicitly-
    cleared draft ({}) renders as empty rather than falling back to published.
    """
    st = svc.get("service_types") or {}
    entry = pick_locale_entry(svc.get("content_entries"), locale, default_locale)

    draft = entry.get("draft_content") if entry else None
    published = entry.get("published_content") if entry else None
    content = draft if draft is not None else (published or {})

    return {
        "id": svc["id"],
        "service_key": svc["service_key"],
        "label": svc.get("label"),
        "service_type_slug": svc["service_type_slug"],
        "service_type_name": st.get("name", svc["service_type_slug"]),
        "service_type_icon": st.get("icon", "Box"),
        "display_order": svc.get("display_order", 0),
        "page_name": svc.get("page_name", "General"),
        "last_updated": entry.get("updated_at") if entry else None,
        "schema": st.get("schema", {}),
        "content": content,
    }


# ── Client workspace endpoints ───────────────────────────────────────────────


@router.get("/projects/{project_slug}/services", response_model=list[ServiceOut])
async def list_services(project_slug: str, request: Request, locale: str | None = None):
    user = await require_user(request)
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    loc = locale or default_locale

    try:
        sb = get_supabase_admin()
        result = (
            sb.table("project_services")
            .select(
                "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon), content_entries(locale, updated_at, draft_content, published_content)"
            )
            .eq("project_id", project["id"])
            .order("display_order")
            .execute()
        )
        return [_flatten_service(s, loc, default_locale) for s in (result.data or [])]
    except Exception as exc:
        # BE-007: don't leak internal exception text to the caller — it
        # surfaces table names, SQL constraints, supabase URLs.
        logger.exception("list_services failed for project %s: %s", project_slug, exc)
        raise HTTPException(status_code=500, detail="Failed to list services") from exc


@router.get("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def get_service(
    project_slug: str, service_key: str, request: Request, locale: str | None = None
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    loc = locale or default_locale

    sb = get_supabase_admin()
    result = (
        sb.table("project_services")
        .select(
            "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema), content_entries(locale, draft_content, published_content, updated_at, translation_meta)"
        )
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    flat = _flatten_service(result.data, loc, default_locale)
    flat["locale"] = loc
    flat["default_locale"] = default_locale
    flat["locales"] = project.get("locales") or [default_locale]
    flat["translation_status"] = _translation_status(
        result.data["service_type_slug"], result.data.get("content_entries"), loc, default_locale
    )
    return flat


@router.put("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def save_service(
    project_slug: str,
    service_key: str,
    body: ContentSaveRequest,
    request: Request,
    seed: bool = False,
    locale: str | None = None,
):
    user = await user_via_bearer_or_session(request)
    if seed and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="seed=true requires admin"
        )
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    locales = project.get("locales") or [default_locale]
    loc = locale or default_locale

    sb = get_supabase_admin()

    # Resolve the project_service (id + type)
    svc_result = (
        sb.table("project_services")
        .select(
            "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema)"
        )
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not svc_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    svc_id = svc_result.data["id"]
    service_type = svc_result.data["service_type_slug"]
    now = datetime.now(UTC).isoformat()

    # Load all existing per-locale rows for this service.
    rows = (
        sb.table("content_entries")
        .select("id, locale, draft_content, published_content, translation_meta")
        .eq("project_service_id", svc_id)
        .execute()
    )
    by_locale = {r["locale"]: r for r in (rows.data or [])}

    # Closure: captures svc_id, now, user, and seed from the enclosing scope.
    def _upsert(target_locale: str, content: dict, meta: dict | None) -> None:
        payload: dict = {
            "project_service_id": svc_id,
            "locale": target_locale,
            "draft_content": content,
            "updated_at": now,
            "updated_by": user.id,
        }
        if meta is not None:
            payload["translation_meta"] = meta
        if seed:
            payload["published_content"] = content
        sb.table("content_entries").upsert(
            payload, on_conflict="project_service_id,locale"
        ).execute()

    if loc == default_locale:
        prev_default = (by_locale.get(default_locale) or {}).get("draft_content") or {}
        _upsert(default_locale, body.content, None)
        # Propagate to every other locale. The provider is only constructed when
        # there is something to translate, so single-locale projects never touch
        # the engine. A translation failure for one locale is logged and skipped —
        # the default save still succeeds and that locale's row is left unchanged.
        other_locales = [t for t in locales if t != default_locale]
        if other_locales:
            provider = get_provider()
            for target in other_locales:
                trow = by_locale.get(target) or {}
                try:
                    new_content, new_meta = sync_locale_draft(
                        service_type,
                        body.content,
                        prev_default,
                        trow.get("draft_content"),
                        trow.get("translation_meta") or {},
                        provider,
                        default_locale,
                        target,
                    )
                    _upsert(target, new_content, new_meta)
                except Exception:  # noqa: BLE001 — resilience: never fail the save
                    logger.exception(
                        "auto-translate failed for %s/%s locale %s (row unchanged)",
                        project_slug,
                        service_key,
                        target,
                    )
    else:
        # Override edit on a non-default locale: any leaf whose value changed
        # versus the stored draft becomes a manual override, anchored to the
        # current default source hash.
        default_content = (by_locale.get(default_locale) or {}).get("draft_content") or {}
        prev_target = (by_locale.get(loc) or {}).get("draft_content") or {}
        prev_meta = dict((by_locale.get(loc) or {}).get("translation_meta") or {})
        new_segs = segments_of(service_type, body.content)
        prev_segs = segments_of(service_type, prev_target)
        src_segs = segments_of(service_type, default_content)
        for path, value in new_segs.items():
            if value != prev_segs.get(path):
                prev_meta[path] = {"src_hash": src_hash(src_segs.get(path, ""))}
        _upsert(loc, body.content, prev_meta)

    # Return fresh state for the edited locale
    return await get_service(project_slug, service_key, request, locale=loc)


@router.post("/projects/{project_slug}/services/{service_key}/upload")
async def upload_file(
    project_slug: str,
    service_key: str,
    request: Request,
    file: UploadFile = File(...),
):
    user = await require_user(request)
    project = require_project_access(project_slug, user)

    # Resolve service + type
    sb = get_supabase_admin()
    svc_result = (
        sb.table("project_services")
        .select("service_type_slug")
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not svc_result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    service_type = svc_result.data["service_type_slug"]

    if service_type not in _ALLOWED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Service type '{service_type}' does not support file uploads.",
        )

    # MIME type validation
    mime = file.content_type or "application/octet-stream"
    if mime in _DENIED_MIME:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{mime}' is not allowed (potential stored-XSS vector).",
        )
    allowed_prefix = _ALLOWED_MIME[service_type]
    if allowed_prefix is not None and not mime.startswith(allowed_prefix):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"File type '{mime}' is not allowed for service type '{service_type}'. Expected: {allowed_prefix}*",
        )

    # Read + size check
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File exceeds the 50 MB limit.",
        )

    # Build storage path: {project_slug}/{service_key}/{uuid}.{ext}
    original_suffix = Path(file.filename or "").suffix.lower()
    ext = original_suffix if original_suffix else _MIME_TO_EXT.get(mime, "")
    storage_path = f"{project_slug}/{service_key}/{uuid.uuid4()}{ext}"

    # Upload via service role client (bypasses RLS)
    sb_admin = get_supabase_admin()
    sb_admin.storage.from_(STORAGE_BUCKET).upload(
        path=storage_path,
        file=content,
        file_options={"content-type": mime, "upsert": "false"},
    )

    public_url = sb_admin.storage.from_(STORAGE_BUCKET).get_public_url(storage_path)

    return {
        "url": public_url,
        "filename": file.filename,
        "size": len(content),
        "mime_type": mime,
    }


# ── Admin-only endpoints ─────────────────────────────────────────────────────


@router.post("/projects/{project_slug}/services", status_code=status.HTTP_201_CREATED)
async def add_service(project_slug: str, body: ServiceCreateRequest, request: Request):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)

    # Validate service_type_slug exists
    sb = get_supabase_admin()
    st_check = (
        sb.table("service_types")
        .select("slug")
        .eq("slug", body.service_type_slug)
        .single()
        .execute()
    )
    if not st_check.data:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Unknown service type"
        )

    # Validate service_key is alphanumeric + underscores only
    import re

    if not re.match(r"^[a-z0-9_]+$", body.service_key):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="service_key must contain only lowercase letters, digits, and underscores",
        )

    # Repeater requires item_schema
    if body.service_type_slug == "repeater":
        if not body.item_schema:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="item_schema is required when creating a repeater service",
            )
        valid_field_types = {"string", "richtext", "url", "tags"}
        for field in body.item_schema:
            if field.type not in valid_field_types:
                raise HTTPException(
                    status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                    detail=f"item_schema field type '{field.type}' is invalid. Must be one of: {', '.join(sorted(valid_field_types))}",
                )

    sb.table("project_services").insert(
        {
            "project_id": project["id"],
            "service_type_slug": body.service_type_slug,
            "service_key": body.service_key,
            "label": body.label,
            "display_order": body.display_order,
            "page_name": body.page_name,
        }
    ).execute()

    # For repeater: seed the content_entries row with _schema + empty items
    if body.service_type_slug == "repeater" and body.item_schema:
        svc_result = (
            sb.table("project_services")
            .select("id")
            .eq("project_id", project["id"])
            .eq("service_key", body.service_key)
            .single()
            .execute()
        )
        if svc_result.data:
            schema_payload = [f.model_dump() for f in body.item_schema]
            default_locale = project.get("default_locale") or "en"
            sb.table("content_entries").insert(
                {
                    "project_service_id": svc_result.data["id"],
                    "locale": default_locale,
                    "published_content": {"_schema": schema_payload, "items": []},
                    "draft_content": {"_schema": schema_payload, "items": []},
                    "updated_at": datetime.now(UTC).isoformat(),
                    "updated_by": user.id,
                }
            ).execute()

    return {"success": True, "service_key": body.service_key}


@router.delete(
    "/projects/{project_slug}/services/{service_key}", status_code=status.HTTP_204_NO_CONTENT
)
async def remove_service(project_slug: str, service_key: str, request: Request):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    sb.table("project_services").delete().eq("project_id", project["id"]).eq(
        "service_key", service_key
    ).execute()


@router.get("/admin/projects", response_model=list[AdminProjectOut])
async def admin_list_projects(request: Request, include_test: bool = False):
    """List every project across all clients.

    By default filters out:
      - inactive (soft-deleted) projects
      - E2E test fixtures (slugs matching `services.test_data.is_test_slug`,
        and projects owned by E2E test users matching `is_test_email`)

    Pass `?include_test=true` to see them too — useful when debugging
    a flaky CI run that may have left orphans.
    """
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("id, name, slug, is_active, created_at, user_id, users(email, full_name)")
        .order("created_at", desc=True)
        .execute()
    )

    out = []
    for p in result.data or []:
        user_row = p.get("users") or {}
        if not include_test:
            if not p.get("is_active"):
                continue
            if is_test_slug(p["slug"]):
                continue
            if is_test_email(user_row.get("email")):
                continue
        out.append(
            {
                "id": p["id"],
                "name": p["name"],
                "slug": p["slug"],
                "is_active": p["is_active"],
                "created_at": p["created_at"],
                "user_id": p["user_id"],
                "user_email": user_row.get("email"),
                "user_full_name": user_row.get("full_name"),
            }
        )
    return out


@router.get("/admin/projects/{project_slug}", response_model=AdminProjectDetailOut)
async def admin_get_project(project_slug: str, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select(
            "slug, name, github_repo, production_branch, vercel_project_id, "
            "production_url, preview_url, preview_token, last_published_at"
        )
        .eq("slug", project_slug)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")
    return result.data


@router.patch("/admin/projects/{project_slug}")
async def admin_patch_project(project_slug: str, body: AdminProjectPatchIn, request: Request):
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    update_data = {k: v for k, v in body.model_dump().items() if v is not None}
    if not update_data:
        return {"updated": 0}
    update_data["updated_at"] = datetime.now(UTC).isoformat()

    sb.table("projects").update(update_data).eq("slug", project_slug).execute()
    return {"updated": len(update_data)}


@router.delete("/admin/projects/{project_slug}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def admin_delete_project(project_slug: str, request: Request):
    """Hard-delete a project + cascade (services, content_entries, etc.).

    Primary use case: integration-test cleanup so CI runs don't leak
    `throwaway-*` slugs into the dashboard. The dashboard does NOT
    expose this; only an admin Bearer key (or admin sid cookie) can
    invoke. PATCH `is_active=false` remains the soft-delete path for
    the dashboard's own deactivate flow.
    """
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    row = sb.table("projects").select("id").eq("slug", project_slug).maybe_single().execute()
    if not (row and row.data):
        raise HTTPException(404, f"Project {project_slug!r} not found")
    sb.table("projects").delete().eq("id", row.data["id"]).execute()


@router.post("/admin/projects", status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def admin_create_project(body: AdminProjectCreateIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()

    owner = (
        sb.table("users")
        .select("id, email")
        .eq("email", body.owner_email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (owner and owner.data):
        raise HTTPException(404, f"No user with email {body.owner_email!r}")

    existing = (
        sb.table("projects").select("id, slug").eq("slug", body.slug).maybe_single().execute()
    )
    if existing and existing.data:
        raise HTTPException(409, f"Project slug {body.slug!r} already exists")

    inserted = (
        sb.table("projects")
        .insert(
            {
                "user_id": owner.data["id"],
                "slug": body.slug,
                "name": body.name,
                "is_active": True,
                "github_repo": body.github_repo,
                "created_at": datetime.now(UTC).isoformat(),
            }
        )
        .execute()
    )
    return inserted.data[0] if inserted.data else {}


@router.post("/admin/projects/{project_slug}/transfer")
@limiter.limit("3/minute")
async def admin_transfer_project(project_slug: str, body: ProjectTransferIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    target = (
        sb.table("users")
        .select("id, email")
        .eq("email", body.to_user_email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (target and target.data):
        raise HTTPException(404, f"No user with email {body.to_user_email!r}")
    updated = (
        sb.table("projects")
        .update(
            {
                "user_id": target.data["id"],
                "updated_at": datetime.now(UTC).isoformat(),
            }
        )
        .eq("slug", project_slug)
        .execute()
    )
    if not updated.data:
        raise HTTPException(404, f"No project with slug {project_slug!r}")
    return updated.data[0]


@router.post("/admin/clients/{email}/welcome")
@limiter.limit("3/minute")
async def admin_send_welcome(email: str, body: WelcomeEmailIn, request: Request):
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    user = (
        sb.table("users")
        .select("id, email, full_name")
        .eq("email", email.lower().strip())
        .maybe_single()
        .execute()
    )
    if not (user and user.data):
        raise HTTPException(404, f"No user with email {email!r}")
    try:
        result = send_welcome_email(
            to_email=user.data["email"],
            full_name=user.data.get("full_name"),
            project_name=body.project_name,
            website_url=body.website_url,
        )
    except RuntimeError as e:
        raise HTTPException(502, f"Resend send failed: {e}") from e
    return {"success": True, "resend_id": result.get("id")}


@router.get("/admin/clients", response_model=list[UserAdminOut])
async def admin_list_clients(request: Request, include_test: bool = False):
    """List every registered user.

    By default hides E2E test accounts (emails matching
    `services.test_data.is_test_email` — e2e-*, throwaway-*, *@cms-test.dev,
    *@cms-test.local). Pass `?include_test=true` to see them — useful
    when an integration test cleanup looks suspicious.
    """
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    users_result = (
        sb.table("users")
        .select("id, email, full_name, is_admin, is_active, created_at")
        .order("created_at", desc=True)
        .execute()
    )

    out = []
    for u in users_result.data or []:
        if not include_test and is_test_email(u.get("email")):
            continue
        count_result = (
            sb.table("projects")
            .select("id", count="exact")
            .eq("user_id", u["id"])
            .eq("is_active", True)
            .execute()
        )
        out.append({**u, "projects_count": count_result.count or 0})
    return out


@router.get("/admin/service-types", response_model=list[ServiceTypeOut])
async def admin_list_service_types(request: Request):
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    result = (
        sb.table("service_types")
        .select("slug, name, description, icon, schema")
        .order("slug")
        .execute()
    )
    return result.data or []


@router.get("/projects/{project_slug}/settings", response_model=ProjectSettingsOut)
async def get_project_settings(project_slug: str, request: Request):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)

    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select("website_url, allowed_origins")
        .eq("id", project["id"])
        .single()
        .execute()
    )
    data = result.data or {}
    return {
        "website_url": data.get("website_url"),
        "allowed_origins": data.get("allowed_origins") or [],
    }


@router.patch("/projects/{project_slug}/settings", response_model=ProjectSettingsOut)
async def update_project_settings(
    project_slug: str,
    body: ProjectSettingsIn,
    request: Request,
):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)

    # Normalise: strip whitespace, remove empty strings
    origins = [o.strip() for o in body.allowed_origins if o.strip()]
    website_url = body.website_url.strip() if body.website_url else None

    sb = get_supabase_admin()
    sb.table("projects").update(
        {
            "website_url": website_url,
            "allowed_origins": origins,
            "updated_at": datetime.now(UTC).isoformat(),
        }
    ).eq("id", project["id"]).execute()

    return {"website_url": website_url, "allowed_origins": origins}


# ── Locale-management endpoints ─────────────────────────────────────────────


@router.get("/projects/{project_slug}/locales", response_model=ProjectLocalesOut)
async def get_project_locales(project_slug: str, request: Request):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)
    return {
        "default_locale": project.get("default_locale") or "en",
        "locales": project.get("locales") or [project.get("default_locale") or "en"],
    }


@router.put("/projects/{project_slug}/locales", response_model=ProjectLocalesOut)
async def set_project_locales(project_slug: str, body: ProjectLocalesIn, request: Request):
    user = await admin_user_via_bearer_or_sid(request)
    project = require_project_access(project_slug, user)
    sb = get_supabase_admin()

    old_locales = set(project.get("locales") or [])
    old_default = project.get("default_locale") or "en"
    new_locales = list(body.locales)
    new_default = body.default_locale

    added = [loc for loc in new_locales if loc not in old_locales]
    removed = [loc for loc in old_locales if loc not in new_locales]

    # Load all services for this project (id + type) once.
    svc_rows = (
        sb.table("project_services")
        .select("id, service_type_slug")
        .eq("project_id", project["id"])
        .execute()
    )
    services = svc_rows.data or []
    now = datetime.now(UTC).isoformat()

    # Remove locales: delete their content_entries rows.
    if removed:
        svc_ids = [s["id"] for s in services]
        if svc_ids:
            sb.table("content_entries").delete().in_("project_service_id", svc_ids).in_(
                "locale", removed
            ).execute()

    # Add locales: translate every service's default-locale draft into each new locale.
    if added and services:
        provider = get_provider()
        for svc in services:
            svc_id = svc["id"]
            stype = svc["service_type_slug"]
            entries = (
                sb.table("content_entries")
                .select("locale, draft_content, published_content, translation_meta")
                .eq("project_service_id", svc_id)
                .execute()
            )
            by_locale = {e["locale"]: e for e in (entries.data or [])}
            default_row = by_locale.get(new_default) or by_locale.get(old_default) or {}
            default_content = default_row.get("draft_content")
            if default_content is None:
                default_content = default_row.get("published_content") or {}
            for target in added:
                if target == new_default:
                    continue
                try:
                    new_content, new_meta = sync_locale_draft(
                        stype, default_content, {}, None, {}, provider, new_default, target
                    )
                    sb.table("content_entries").upsert(
                        {
                            "project_service_id": svc_id,
                            "locale": target,
                            "draft_content": new_content,
                            "translation_meta": new_meta,
                            "updated_at": now,
                            "updated_by": user.id,
                        },
                        on_conflict="project_service_id,locale",
                    ).execute()
                except Exception:  # noqa: BLE001 — best-effort; never fail the whole op
                    logger.exception(
                        "translate-on-add failed for %s/%s locale %s", project_slug, svc_id, target
                    )

    sb.table("projects").update(
        {"locales": new_locales, "default_locale": new_default, "updated_at": now}
    ).eq("id", project["id"]).execute()

    return {"default_locale": new_default, "locales": new_locales}


@router.post(
    "/projects/{project_slug}/services/{service_key}/retranslate",
    response_model=ServiceDetailOut,
)
async def retranslate_service(project_slug: str, service_key: str, request: Request, locale: str):
    user = await require_user(request)
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    if locale == default_locale:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot re-translate the default locale",
        )

    sb = get_supabase_admin()
    svc = (
        sb.table("project_services")
        .select("id, service_type_slug")
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not svc.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")
    svc_id = svc.data["id"]
    stype = svc.data["service_type_slug"]

    entries = (
        sb.table("content_entries")
        .select("locale, draft_content, published_content")
        .eq("project_service_id", svc_id)
        .execute()
    )
    by_locale = {e["locale"]: e for e in (entries.data or [])}
    default_row = by_locale.get(default_locale) or {}
    default_content = default_row.get("draft_content")
    if default_content is None:
        default_content = default_row.get("published_content") or {}

    # Reset overrides (target_meta={}) and re-translate everything fresh from default.
    new_content, new_meta = sync_locale_draft(
        stype, default_content, {}, None, {}, get_provider(), default_locale, locale
    )
    sb.table("content_entries").upsert(
        {
            "project_service_id": svc_id,
            "locale": locale,
            "draft_content": new_content,
            "translation_meta": new_meta,
            "updated_at": datetime.now(UTC).isoformat(),
            "updated_by": user.id,
        },
        on_conflict="project_service_id,locale",
    ).execute()
    return await get_service(project_slug, service_key, request, locale=locale)


# ── Admin client management ──────────────────────────────────────────────────


def _generate_password(length: int = 16) -> str:
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return "".join(secrets.choice(alphabet) for _ in range(length))


@router.get("/admin/clients/lookup", response_model=CreateClientOut)
async def lookup_client(email: str, request: Request):
    """Check whether an email already has an account. Returns account info (no password)."""
    await admin_user_via_bearer_or_sid(request)

    sb = get_supabase_admin()
    result = (
        sb.table("users")
        .select("id, email, full_name")
        .eq("email", email.lower().strip())
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

    u = result.data[0]
    return CreateClientOut(
        id=u["id"],
        email=u["email"],
        full_name=u.get("full_name"),
        created=False,
        generated_password=None,
    )


@router.post("/admin/clients", response_model=CreateClientOut, status_code=status.HTTP_201_CREATED)
@limiter.limit("3/minute")
async def create_client(body: CreateClientRequest, request: Request):
    """
    Create a new client account (if email not found) or return the existing one.
    When a new account is created, a random password is generated and returned once.
    """
    await admin_user_via_bearer_or_sid(request)

    email = body.email.lower().strip()
    sb = get_supabase_admin()

    # Check for existing user
    existing = (
        sb.table("users").select("id, email, full_name").eq("email", email).limit(1).execute()
    )
    if existing.data:
        u = existing.data[0]
        return CreateClientOut(
            id=u["id"],
            email=u["email"],
            full_name=u.get("full_name"),
            created=False,
            generated_password=None,
        )

    # Generate id + password locally and hash with the same argon2 helper that
    # /auth/login uses (auth_service.services.auth_service). Writing
    # password_hash satisfies the NOT NULL constraint on public.users.
    user_id = str(uuid.uuid4())
    password = _generate_password()
    password_hash = hash_password(password)

    # Insert into public users table (service-role client to bypass RLS).
    sb_admin = get_supabase_admin()
    sb_admin.table("users").insert(
        {
            "id": user_id,
            "email": email,
            "full_name": body.full_name,
            "password_hash": password_hash,
            "is_admin": False,
            "is_active": True,
            "created_at": datetime.now(UTC).isoformat(),
        }
    ).execute()

    return CreateClientOut(
        id=user_id,
        email=email,
        full_name=body.full_name,
        created=True,
        generated_password=password,
    )


@router.delete("/admin/clients/{email}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("3/minute")
async def delete_client(email: str, request: Request):
    """Hard-delete a client account.

    Removes both the Supabase Auth user and the `public.users` row
    (FK CASCADE handles sessions, admin_api_keys, project ownership
    is reassigned to the deleting admin via Supabase ON DELETE rules).

    Primary use case: integration-test cleanup so CI runs don't leak
    `throwaway-create-*@cms-test.dev` rows. Only an admin key can
    invoke this; the dashboard does not expose it.
    """
    await admin_user_via_bearer_or_sid(request)
    sb = get_supabase_admin()
    sb_admin = get_supabase_admin()

    target_email = email.lower().strip()
    row = sb.table("users").select("id, email").eq("email", target_email).maybe_single().execute()
    if not (row and row.data):
        raise HTTPException(404, f"No user with email {email!r}")

    user_id = row.data["id"]
    # Try the Supabase auth admin delete (cascades to public.users via
    # FK ON DELETE CASCADE on the public.users.id reference). Most
    # records have a parallel auth.users row from the original
    # provisioning flow.
    #
    # `create_client` (the dashboard create-flow) writes ONLY to
    # public.users — no auth.users row. Calling auth.admin.delete_user
    # on a non-auth user raises and would 500 the entire request,
    # leaving the public.users row alive AND blocking integration-
    # test cleanup. Catch and continue; the explicit table delete
    # below covers both cases idempotently.
    try:
        sb_admin.auth.admin.delete_user(user_id)
    except Exception as exc:  # noqa: BLE001 — broad on purpose
        logger.warning(
            "auth admin delete skipped for user %s (%s): %s",
            user_id,
            email,
            exc,
        )
    # Authoritative delete from public.users. Idempotent — already-gone
    # is fine.
    sb_admin.table("users").delete().eq("id", user_id).execute()
