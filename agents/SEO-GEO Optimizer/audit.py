# agents/SEO-GEO Optimizer/audit.py
"""Deterministic SEO + local scoring from render_check signals. GEO score comes from
the LLM judge (the skill) and is just packaged here. Stdlib only, pure functions.

Each item maps to the design spec's rubric (docs/.../2026-06-14-seo-geo-agent-design.md).
Refuted claims are NOT scored. Schema is a structured signal, not an AI-citation multiplier.
"""

from __future__ import annotations


def _clamp(n: int) -> int:
    return max(0, min(100, int(round(n))))


# (rubric_id, weight, predicate)
_SEO_ITEMS = [
    ("G-1_content_in_raw_html", 18, lambda s: bool(s.get("has_main_content"))),
    ("G-3_single_h1", 8, lambda s: s.get("h1_count") == 1),
    ("G-3_heading_order", 8, lambda s: bool(s.get("heading_order_ok"))),
    ("G-4_title_len", 10, lambda s: 40 <= s.get("title_len", 0) <= 60),
    ("G-4_meta_desc_len", 10, lambda s: 120 <= s.get("meta_desc_len", 0) <= 165),
    ("G-5_canonical", 8, lambda s: bool(s.get("canonical"))),
    ("G-6_jsonld_valid", 12, lambda s: bool(s.get("jsonld_types")) and bool(s.get("jsonld_valid"))),
    ("G-8_internal_links", 6, lambda s: s.get("internal_link_count", 0) >= 1),
    ("G-onpage_og", 6, lambda s: bool(s.get("og_present"))),
]

_LOCAL_ITEMS = [
    ("L-1_localbusiness_jsonld", 60, lambda s: bool(s.get("has_localbusiness"))),
    ("L-onpage_has_content", 40, lambda s: bool(s.get("has_main_content"))),
]


def _score(items: list, signals: dict) -> tuple[int, dict]:
    earned = 0
    possible = 0
    detail: dict[str, str] = {}
    for rid, w, pred in items:
        possible += w
        ok = bool(pred(signals))
        earned += w if ok else 0
        detail[rid] = "pass" if ok else "fail"
    return _clamp(100 * earned / possible if possible else 0), detail


def score_seo(signals: dict) -> tuple[int, dict]:
    return _score(_SEO_ITEMS, signals)


def score_local(signals: dict) -> tuple[int, dict]:
    return _score(_LOCAL_ITEMS, signals)


def assemble_audit(seo: int, geo: int, local: int, scores_detail: dict) -> dict:
    """Package the three sub-scores (geo from the LLM judge) into a seo_audits row payload."""
    return {
        "seo_score": _clamp(seo),
        "geo_score": _clamp(geo),
        "local_score": _clamp(local),
        "scores_detail": scores_detail or {},
    }
