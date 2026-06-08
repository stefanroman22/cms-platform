"""Pick the right per-locale content_entries row from a PostgREST embed.

After the Phase-1 migration, project_services embeds a LIST of content_entries
rows (one per locale) instead of a single one-to-one dict. This helper resolves
the row for a requested locale, falling back to the project's default locale when
that locale has no row yet, and finally to a legacy single dict for back-compat
during the migration window. Pure — no I/O.
"""

from __future__ import annotations


def pick_locale_entry(
    embedded: dict | list | None, locale: str, default_locale: str
) -> dict | None:
    """Return the content_entries row for `locale`, else the default-locale row.

    `embedded` is the raw value of svc["content_entries"]:
      - list → post-migration: one row per locale (each has a "locale" key)
      - dict → legacy one-to-one embed (no "locale" key)
      - None → no content yet
    """
    if embedded is None:
        return None
    rows = embedded if isinstance(embedded, list) else [embedded]
    if not rows:
        return None

    by_locale = {r.get("locale"): r for r in rows if isinstance(r, dict)}
    if locale in by_locale:
        return by_locale[locale]
    if default_locale in by_locale:
        return by_locale[default_locale]
    # Back-compat: legacy embed with no "locale" key — return the first row.
    first = rows[0]
    return first if isinstance(first, dict) else None
