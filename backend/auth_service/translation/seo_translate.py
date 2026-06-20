# backend/auth_service/translation/seo_translate.py
"""Translate ONLY the human-readable PROSE fields of a flat seo_page_meta / seo_articles
row from the website's default locale into a target locale, using the existing translation
provider. PURE w.r.t. inputs (provider is injected).

Policy (research-verified): localize prose (title/description/OG text/article body); keep
CODED FACTS invariant (canonical, robots, og.image, json_ld data, hero_image_url, og:locale,
hreflang, inLanguage) — those are generated per-page or repeated verbatim, NEVER translated.

Failure rule: OMIT a field whose translation fails or is empty (never write "" / null), so the
read-layer per-field default-locale fallback can fire and the page is never broken/empty.
"""

from __future__ import annotations

# (field, format) prose specs per kind. Everything not listed here is invariant.
_META_FIELDS = (("title", "text"), ("description", "text"))
_META_OG_FIELDS = (("title", "text"), ("description", "text"))
_ARTICLE_FIELDS = (("title", "text"), ("excerpt", "text"), ("body", "markdown"))


def _one(provider, text: str, *, source: str, target: str, fmt: str) -> str | None:
    if not text:
        return None
    try:
        res = provider.translate([text], source=source, target=target, fmt=fmt)
    except Exception:  # noqa: BLE001 — any provider/network error => omit (fallback fires)
        return None
    out = (res or [None])[0]
    return out or None


def translate_seo_prose(
    default_content: dict, *, kind: str, source: str, target: str, provider
) -> dict:
    """Return {field: translated} for the prose fields that translated successfully.
    Omits any field that is empty in the source or whose translation failed."""
    out: dict = {}
    if kind == "meta":
        for field, fmt in _META_FIELDS:
            t = _one(provider, default_content.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                out[field] = t
        og = default_content.get("og") or {}
        tog: dict = {}
        for field, fmt in _META_OG_FIELDS:
            t = _one(provider, og.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                tog[field] = t
        if tog:
            out["og"] = tog
    elif kind == "article":
        for field, fmt in _ARTICLE_FIELDS:
            t = _one(provider, default_content.get(field), source=source, target=target, fmt=fmt)
            if t is not None:
                out[field] = t
    return out
