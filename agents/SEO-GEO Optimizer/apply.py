# agents/SEO-GEO Optimizer/apply.py
"""Build the Supabase payloads the apply phase writes (seo_page_meta / seo_articles),
and compute before/after diffs for the seo_changes audit trail. PURE / stdlib only.
Everything is written as DRAFT (status='draft'); publishing happens only after the
visual-QA gate is green (phase 6). updated_by defaults to 'agent'.
"""

from __future__ import annotations

import json


def sql_str(value: object) -> str:
    """Render ``value`` as a SAFE single-quoted Postgres string literal (SEC-057).

    Every value that reaches agent-emitted SQL — competitor name/url/city/analysis,
    routes, titles, triggers — originates in web- or LLM-derived text the operator
    does NOT control. Doubling embedded single quotes (correct under Postgres'
    default ``standard_conforming_strings=on``) and forbidding a NUL byte means such
    a value can never close the literal or append a stacked statement. Use this for
    EVERY interpolated value; NEVER hand-template ``'<value>'`` into SQL.
    """
    s = "" if value is None else str(value)
    if "\x00" in s:
        raise ValueError("NUL byte is not allowed in a SQL string literal")
    return "'" + s.replace("'", "''") + "'"


def build_competitor_payload(
    project_id: str,
    run_id: str,
    name: str,
    url: str,
    location: str,
    signals: dict | list | None,
    analysis: str,
) -> dict:
    """One ``seo_competitors`` row. ``name``/``url``/``location``/``analysis`` are
    attacker-influenced (they come from competitor sites fetched in Phase 2), so they
    are persisted ONLY through :func:`build_competitor_insert_sql`, never templated."""
    return {
        "project_id": project_id,
        "run_id": run_id,
        "name": name,
        "url": url,
        "location": location,
        "signals": signals if isinstance(signals, dict | list) else {},
        "analysis": analysis or "",
    }


def build_competitor_insert_sql(payload: dict) -> str:
    """Render a parameter-safe INSERT for one ``seo_competitors`` row (SEC-057).

    Replaces the old raw-``'<name>'`` templating in phase 2: every value is escaped via
    :func:`sql_str` (the ``signals`` jsonb is ``json.dumps``'d, escaped, then cast
    ``::jsonb``), so a malicious competitor ``name``/``url``/``city``/``analysis`` (or an
    everyday apostrophe like ``O'Brien's``) cannot break out of the literal or inject SQL
    against the service-role, RLS-bypassing MCP path. Pass the returned string verbatim to
    ``mcp__supabase__execute_sql``."""
    signals_json = json.dumps(payload.get("signals") or {}, ensure_ascii=False)
    columns = "project_id, run_id, name, url, location, signals, analysis, captured_at"
    values = ", ".join(
        [
            sql_str(payload["project_id"]),
            sql_str(payload["run_id"]),
            sql_str(payload["name"]),
            sql_str(payload["url"]),
            sql_str(payload["location"]),
            sql_str(signals_json) + "::jsonb",
            sql_str(payload["analysis"]),
            "now()",
        ]
    )
    return f"INSERT INTO seo_competitors ({columns}) VALUES ({values});"


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
