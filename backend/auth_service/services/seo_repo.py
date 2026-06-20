# backend/auth_service/services/seo_repo.py
"""Supabase access for the SEO/GEO router. Mirrors booking_admin_repo.py."""

from __future__ import annotations

from datetime import UTC, datetime

from .supabase_client import get_supabase_admin


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ── reads (analytical tables; the agent writes these via Supabase MCP) ──
def latest_run(project_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_runs")
        .select("*")
        .eq("project_id", project_id)
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def latest_audit(project_id: str) -> dict | None:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_audits")
        .select("*")
        .eq("project_id", project_id)
        .order("audited_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def plan_items(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_plan_items")
        .select("*")
        .eq("project_id", project_id)
        .order("priority", desc=True)
        .execute()
    )
    return res.data or []


def runs(project_id: str, limit: int = 20) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_runs")
        .select("*")
        .eq("project_id", project_id)
        .order("started_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def changes(project_id: str, limit: int = 50) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_changes")
        .select("*")
        .eq("project_id", project_id)
        .order("applied_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


def competitors(project_id: str, limit: int = 50) -> list[dict]:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_competitors")
        .select("*")
        .eq("project_id", project_id)
        .order("captured_at", desc=True)
        .limit(limit)
        .execute()
    )
    return res.data or []


# ── content CRUD (page_meta + articles; humans via dashboard, agent via bearer) ──
def list_page_meta(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = sb.table("seo_page_meta").select("*").eq("project_id", project_id).execute()
    return res.data or []


def upsert_page_meta(project_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {**fields, "project_id": project_id, "updated_by": updated_by, "updated_at": _now()}
    res = sb.table("seo_page_meta").upsert(payload, on_conflict="project_id,route,locale").execute()
    return (res.data or [{}])[0]


def delete_page_meta(project_id: str, meta_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("seo_page_meta").delete().eq("project_id", project_id).eq("id", meta_id).execute()


def list_articles(project_id: str) -> list[dict]:
    sb = get_supabase_admin()
    res = sb.table("seo_articles").select("*").eq("project_id", project_id).execute()
    return res.data or []


def create_article(project_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {
        **fields,
        "project_id": project_id,
        "updated_by": updated_by,
        "created_at": _now(),
        "updated_at": _now(),
    }
    res = sb.table("seo_articles").insert(payload).execute()
    return (res.data or [{}])[0]


def update_article(project_id: str, article_id: str, fields: dict, updated_by: str) -> dict:
    sb = get_supabase_admin()
    payload = {**fields, "updated_by": updated_by, "updated_at": _now()}
    res = (
        sb.table("seo_articles")
        .update(payload)
        .eq("project_id", project_id)
        .eq("id", article_id)
        .execute()
    )
    return (res.data or [{}])[0]


def delete_article(project_id: str, article_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("seo_articles").delete().eq("project_id", project_id).eq("id", article_id).execute()


def enqueue_job(project_id: str, kind: str, requested_by: str) -> dict:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_jobs")
        .insert({"project_id": project_id, "kind": kind, "requested_by": requested_by})
        .execute()
    )
    return (res.data or [{}])[0]


# ── public site consumer (published only) ──
def project_default_locale(project_id: str) -> str:
    sb = get_supabase_admin()
    res = (
        sb.table("projects").select("default_locale").eq("id", project_id).maybe_single().execute()
    )
    return (res.data or {}).get("default_locale") or "en"


_META_PUBLIC_COLS = "title, description, canonical, og, json_ld, robots"


def _published_meta_row(project_id: str, route: str, locale: str) -> dict | None:
    sb = get_supabase_admin()
    res = (
        sb.table("seo_page_meta")
        .select(_META_PUBLIC_COLS)
        .eq("project_id", project_id)
        .eq("route", route)
        .eq("locale", locale)
        .eq("status", "published")
        .limit(1)
        .execute()
    )
    rows = res.data or []
    return rows[0] if rows else None


def _merge_nonempty(base: dict, over: dict) -> dict:
    """Overlay `over` onto `base` per field, ignoring empty values (so default survives).
    og is merged one level deep (translated og.title/description over default og.image)."""
    merged = dict(base or {})
    for k, v in (over or {}).items():
        if v in (None, "", {}, []):
            continue
        if k == "og" and isinstance(v, dict) and isinstance(merged.get("og"), dict):
            og = dict(merged["og"])
            for ok, ov in v.items():
                if ov not in (None, "", {}, []):
                    og[ok] = ov
            merged["og"] = og
        else:
            merged[k] = v
    return merged


def published_meta(project_id: str, route: str, locale: str) -> dict | None:
    """Requested-locale published meta with PER-FIELD fallback to the default locale.
    A missing/failed-translation locale transparently shows default-locale text (never empty)."""
    default_locale = project_default_locale(project_id)
    target = _published_meta_row(project_id, route, locale)
    base = (
        _published_meta_row(project_id, route, default_locale) if default_locale != locale else None
    )
    if not target and not base:
        return None
    return _merge_nonempty(base or {}, target or {})


_ARTICLE_PUBLIC_COLS = "slug, locale, title, excerpt, body, json_ld, hero_image_url"


def published_articles(project_id: str, locale: str) -> list[dict]:
    """Published articles for a locale, each per-field-filled from the default-locale article
    of the same slug (so an untranslated article shows default-locale prose, never empty)."""
    sb = get_supabase_admin()
    default_locale = project_default_locale(project_id)

    def rows_for(loc: str) -> dict[str, dict]:
        res = (
            sb.table("seo_articles")
            .select(_ARTICLE_PUBLIC_COLS)
            .eq("project_id", project_id)
            .eq("locale", loc)
            .eq("status", "published")
            .execute()
        )
        return {r["slug"]: r for r in (res.data or [])}

    target = rows_for(locale)
    base = rows_for(default_locale) if default_locale != locale else {}
    slugs = set(target) | set(base)
    out: list[dict] = []
    for slug in slugs:
        merged = _merge_nonempty(base.get(slug, {}), target.get(slug, {}))
        if merged:
            merged["slug"] = slug
            out.append(merged)
    return out
