# agents/SEO-GEO Optimizer/site_change_spec.py
"""The site-change-spec contract: the JSON the SEO/GEO agent emits for new_page / section
plan items, which the Website Builder (incremental mode) and CMS Connector consume. PURE.

One interface, no ad-hoc repo edits. The agent NEVER hand-edits client Next.js routing —
new-page CODE only flows through the Builder (then the visual-QA gate before publish).
"""

from __future__ import annotations

PAGE_TYPES = {"blog_index", "blog_post", "local_landing", "service", "section"}
CONSUMES = {"seo_articles", "seo_page_meta", "static", None}
DEFAULT_BRANCH = "cms-preview"


def build_site_change_spec(
    *,
    project_slug: str,
    repo: str,
    run_id: str,
    pages=None,
    sections=None,
    cms_wiring=None,
    reason: str = "",
    branch: str = DEFAULT_BRANCH,
) -> dict:
    return {
        "project_slug": project_slug,
        "repo": repo,
        "branch": branch,
        "run_id": run_id,
        "pages": list(pages or []),
        "sections": list(sections or []),
        "cms_wiring": list(cms_wiring or []),
        "reason": reason,
    }


def validate_site_change_spec(spec: dict) -> tuple[bool, list[str]]:
    errs: list[str] = []
    for key in ("project_slug", "repo", "run_id"):
        if not spec.get(key):
            errs.append(f"missing required field: {key}")
    if not spec.get("reason"):
        errs.append("missing required field: reason")
    if spec.get("branch") and spec["branch"] != DEFAULT_BRANCH:
        errs.append(f"branch must be {DEFAULT_BRANCH!r} (code changes go via the preview branch)")
    pages = spec.get("pages") or []
    sections = spec.get("sections") or []
    if not pages and not sections:
        errs.append("spec has neither pages nor sections — nothing to build")
    for i, p in enumerate(pages):
        if not p.get("route"):
            errs.append(f"pages[{i}]: missing route")
        if p.get("page_type") not in PAGE_TYPES:
            errs.append(
                f"pages[{i}]: invalid page_type {p.get('page_type')!r} (allowed: {sorted(PAGE_TYPES)})"
            )
        if "consumes" in p and p.get("consumes") not in CONSUMES:
            errs.append(f"pages[{i}]: invalid consumes {p.get('consumes')!r}")
        if not p.get("locales"):
            errs.append(f"pages[{i}]: missing locales")
    for i, w in enumerate(spec.get("cms_wiring") or []):
        if w.get("consumes") not in CONSUMES:
            errs.append(f"cms_wiring[{i}]: invalid consumes {w.get('consumes')!r}")
    return (not errs), errs
