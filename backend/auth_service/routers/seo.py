# backend/auth_service/routers/seo.py
"""SEO/GEO router: dashboard reads + human CRUD + public site-consumer endpoints.

Auth: human + agent endpoints use user_via_bearer_or_session + require_project_access
(session for the dashboard, admin bearer for the agent). Public consumer endpoints
are unauthenticated (published content only), mirroring content.py.
"""

from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request, status

from ..models.seo_schemas import (
    SeoArticleIn,
    SeoArticleOut,
    SeoCompetitorOut,
    SeoHistoryOut,
    SeoJobIn,
    SeoJobOut,
    SeoOverviewOut,
    SeoPageMetaIn,
    SeoPageMetaOut,
    SeoPlanItemOut,
    SeoTranslateIn,
)
from ..services import seo_repo
from ..services.supabase_client import get_supabase_admin
from ..translation import get_provider, seo_translate
from .deps import require_project_access, user_via_bearer_or_session

router = APIRouter(tags=["seo"])


async def _scope(project_slug: str, request: Request) -> dict:
    """Auth + project scope. Returns the project row."""
    user = await user_via_bearer_or_session(request)
    return require_project_access(project_slug, user)


def _project_flags(project_id: str) -> dict:
    sb = get_supabase_admin()
    res = (
        sb.table("projects")
        .select("seo_enabled, seo_blog_route, seo_last_run_at")
        .eq("id", project_id)
        .maybe_single()
        .execute()
    )
    return res.data or {"seo_enabled": False, "seo_blog_route": None, "seo_last_run_at": None}


@router.get("/projects/{project_slug}/seo/overview", response_model=SeoOverviewOut)
async def overview(project_slug: str, request: Request) -> SeoOverviewOut:
    project = await _scope(project_slug, request)
    flags = _project_flags(project["id"])
    run = seo_repo.latest_run(project["id"])
    audit = seo_repo.latest_audit(project["id"])
    return SeoOverviewOut(
        enabled=bool(flags.get("seo_enabled")),
        blog_route=flags.get("seo_blog_route"),
        last_run_at=flags.get("seo_last_run_at"),
        seo_score=(audit or {}).get("seo_score") if audit else None,
        geo_score=(audit or {}).get("geo_score") if audit else None,
        local_score=(audit or {}).get("local_score") if audit else None,
        last_status=(run or {}).get("status") if run else None,
        locales=list(project.get("locales") or []),
    )


@router.get("/projects/{project_slug}/seo/plan", response_model=list[SeoPlanItemOut])
async def plan(project_slug: str, request: Request) -> list[SeoPlanItemOut]:
    project = await _scope(project_slug, request)
    return [SeoPlanItemOut(**it) for it in seo_repo.plan_items(project["id"])]


@router.get("/projects/{project_slug}/seo/history", response_model=SeoHistoryOut)
async def history(project_slug: str, request: Request) -> SeoHistoryOut:
    project = await _scope(project_slug, request)
    return SeoHistoryOut(
        runs=seo_repo.runs(project["id"]),
        changes=seo_repo.changes(project["id"]),
    )


@router.get("/projects/{project_slug}/seo/competitors", response_model=list[SeoCompetitorOut])
async def competitors(project_slug: str, request: Request) -> list[SeoCompetitorOut]:
    project = await _scope(project_slug, request)
    return [SeoCompetitorOut(**c) for c in seo_repo.competitors(project["id"])]


@router.get("/projects/{project_slug}/seo/meta", response_model=list[SeoPageMetaOut])
async def list_meta(project_slug: str, request: Request) -> list[SeoPageMetaOut]:
    project = await _scope(project_slug, request)
    return [SeoPageMetaOut(**m) for m in seo_repo.list_page_meta(project["id"])]


@router.put("/projects/{project_slug}/seo/meta", response_model=SeoPageMetaOut)
async def put_meta(project_slug: str, body: SeoPageMetaIn, request: Request) -> SeoPageMetaOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.upsert_page_meta(project["id"], body.model_dump(), user.email)
    return SeoPageMetaOut(**row)


@router.delete("/projects/{project_slug}/seo/meta/{meta_id}")
async def del_meta(project_slug: str, meta_id: str, request: Request) -> dict:
    project = await _scope(project_slug, request)
    seo_repo.delete_page_meta(project["id"], meta_id)
    return {"deleted": True}


@router.get("/projects/{project_slug}/seo/articles", response_model=list[SeoArticleOut])
async def list_articles(project_slug: str, request: Request) -> list[SeoArticleOut]:
    project = await _scope(project_slug, request)
    return [SeoArticleOut(**a) for a in seo_repo.list_articles(project["id"])]


@router.post("/projects/{project_slug}/seo/articles", response_model=SeoArticleOut)
async def create_article(project_slug: str, body: SeoArticleIn, request: Request) -> SeoArticleOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.create_article(project["id"], body.model_dump(), user.email)
    return SeoArticleOut(**row)


@router.put("/projects/{project_slug}/seo/articles/{article_id}", response_model=SeoArticleOut)
async def update_article(
    project_slug: str, article_id: str, body: SeoArticleIn, request: Request
) -> SeoArticleOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.update_article(project["id"], article_id, body.model_dump(), user.email)
    if not row:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Article not found")
    return SeoArticleOut(**row)


@router.delete("/projects/{project_slug}/seo/articles/{article_id}")
async def del_article(project_slug: str, article_id: str, request: Request) -> dict:
    project = await _scope(project_slug, request)
    seo_repo.delete_article(project["id"], article_id)
    return {"deleted": True}


@router.post("/projects/{project_slug}/seo/jobs", response_model=SeoJobOut)
async def enqueue_job(project_slug: str, body: SeoJobIn, request: Request) -> SeoJobOut:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    row = seo_repo.enqueue_job(project["id"], body.kind, user.email)
    return SeoJobOut(
        id=row["id"], kind=row["kind"], status=row["status"], requested_at=row["requested_at"]
    )


def _project_id_by_slug(slug: str) -> str | None:
    sb = get_supabase_admin()
    res = (
        sb.table("projects")
        .select("id")
        .eq("slug", slug)
        .eq("is_active", True)
        .maybe_single()
        .execute()
    )
    return (res.data or {}).get("id")


@router.get("/projects/{project_slug}/seo/public/meta")
async def public_meta(project_slug: str, route: str, locale: str) -> dict:
    pid = _project_id_by_slug(project_slug)
    if not pid:
        return {}
    return seo_repo.published_meta(pid, route, locale) or {}


@router.get("/projects/{project_slug}/seo/public/articles")
async def public_articles(project_slug: str, locale: str) -> dict:
    pid = _project_id_by_slug(project_slug)
    if not pid:
        return {"articles": []}
    return {"articles": seo_repo.published_articles(pid, locale)}


def _project_locales(project_id: str) -> tuple[str, list[str]]:
    sb = get_supabase_admin()
    res = (
        sb.table("projects")
        .select("default_locale, locales")
        .eq("id", project_id)
        .maybe_single()
        .execute()
    )
    row = res.data or {}
    return (row.get("default_locale") or "en", list(row.get("locales") or []))


def _translate_seo_for_project(project: dict, kind: str) -> dict:
    """Fill non-default locales for every default-locale seo row of `kind` via the provider.
    Skips a target row a HUMAN edited (updated_by not agent*) so manual edits are preserved.
    Omit-on-failure: a failed field is left unwritten (read-layer falls back to default)."""
    sb = get_supabase_admin()
    pid = project["id"]
    default_locale, locales = _project_locales(pid)
    targets = [loc for loc in locales if loc and loc != default_locale]
    if not targets:
        return {"translated": 0}
    provider = get_provider()
    table = "seo_page_meta" if kind == "meta" else "seo_articles"
    defaults = (
        sb.table(table)
        .select("*")
        .eq("project_id", pid)
        .eq("locale", default_locale)
        .execute()
        .data
        or []
    )
    count = 0
    for d in defaults:
        key = {"route": d["route"]} if kind == "meta" else {"slug": d["slug"]}
        for loc in targets:
            q = sb.table(table).select("updated_by").eq("project_id", pid).eq("locale", loc)
            for k, v in key.items():
                q = q.eq(k, v)
            existing = q.limit(1).execute().data or []
            if existing and not str(existing[0].get("updated_by", "")).startswith("agent"):
                continue  # preserve a human-edited translation
            prose = seo_translate.translate_seo_prose(
                d, kind=kind, source=default_locale, target=loc, provider=provider
            )
            if not prose:
                continue
            payload = {
                **key,
                "project_id": pid,
                "locale": loc,
                "status": d.get("status", "draft"),
                "updated_by": "agent-translation",
                **prose,
            }
            conflict = "project_id,route,locale" if kind == "meta" else "project_id,slug,locale"
            sb.table(table).upsert(payload, on_conflict=conflict).execute()
            count += 1
    return {"translated": count}


@router.post("/projects/{project_slug}/seo/translate")
async def translate_seo(project_slug: str, body: SeoTranslateIn, request: Request) -> dict:
    user = await user_via_bearer_or_session(request)
    project = require_project_access(project_slug, user)
    return _translate_seo_for_project(project, body.kind)
