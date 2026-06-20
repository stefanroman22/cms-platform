# agents/SEO-GEO Optimizer/apply.py
"""Build the Supabase payloads the apply phase writes (seo_page_meta / seo_articles),
and compute before/after diffs for the seo_changes audit trail. PURE / stdlib only.
Everything is written as DRAFT (status='draft'); publishing happens only after the
visual-QA gate is green (phase 6). updated_by defaults to 'agent'.
"""

from __future__ import annotations


def build_page_meta_payload(project_id: str, route: str, locale: str, fields: dict) -> dict:
    allowed = ("title", "description", "canonical", "og", "json_ld", "robots")
    out = {
        "project_id": project_id,
        "route": route,
        "locale": locale,
        "status": "draft",
        "updated_by": "agent",
    }
    for k in allowed:
        if k in fields:
            out[k] = fields[k]
    return out


def build_article_payload(
    project_id: str, run_id: str, slug: str, locale: str, fields: dict
) -> dict:
    allowed = ("title", "excerpt", "body", "json_ld", "hero_image_url")
    out = {
        "project_id": project_id,
        "source_run_id": run_id,
        "slug": slug,
        "locale": locale,
        "status": "draft",
        "updated_by": "agent",
    }
    for k in allowed:
        if k in fields:
            out[k] = fields[k]
    return out


def diff_before_after(before: dict, after: dict) -> dict:
    """Only changed/added fields. Used for the seo_changes.before/after record."""
    diff: dict[str, dict] = {}
    for k in set(before) | set(after):
        b = before.get(k)
        a = after.get(k)
        if b != a:
            diff[k] = {"before": b, "after": a}
    return diff
