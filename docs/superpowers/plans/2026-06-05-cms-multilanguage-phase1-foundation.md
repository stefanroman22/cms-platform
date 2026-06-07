# CMS Multi-Language — Phase 1 (Foundation) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Introduce a per-locale dimension across the CMS persistence and API layers — without changing any externally observable behavior — and add the pure foundation libraries (segment model + translation provider scaffold) that Phases 2–5 build on.

**Architecture:** Spec at [docs/superpowers/specs/2026-06-05-cms-multilanguage-design.md](../specs/2026-06-05-cms-multilanguage-design.md). This is **Phase 1 of 5** (Foundation). It adds `projects.default_locale`/`locales[]` and `content_entries.locale`/`translation_meta`, swaps the `content_entries` uniqueness from one-row-per-service to one-row-per-(service × locale), and makes **every** content read/write path locale-aware while defaulting to each project's `default_locale`. Existing single-locale sites are tagged with their default locale and keep working byte-for-byte. **No auto-translation, no new public endpoints, no dashboard changes yet** — those are Phases 2–5, each with its own plan + PR.

**Tech Stack:** Python 3.13 · FastAPI · supabase-py (PostgREST, service-role) · Supabase Postgres 17 (migrations applied via the Supabase MCP, never psql) · pytest with `mock_supabase`/`client`/`auth_as` fixtures.

---

## Conventions for this plan

- **Run backend tests:** `cd backend && python -m pytest auth_service/tests/<file> -v` (venv active). Full suite: `make test-backend`.
- **Migrations:** write the `.sql` file under `backend/migrations/`, then apply it with the Supabase MCP `apply_migration` tool (project `CMS`, ref `xeluydwpgiddbamysgyu`). Do **not** run psql by hand.
- **Commits:** per project convention, do **not** auto-commit. The `git commit` steps below are prepared checkpoints — stage and run them only when Stefan approves the batch.
- **TDD:** write the failing test, see it fail, implement minimally, see it pass.

## File structure (Phase 1)

**Create:**
- `backend/migrations/2026_06_05_content_locale.sql` — schema migration (locale dimension + uniqueness swap + backfill).
- `backend/auth_service/services/segments.py` — pure: `segments_of()` + `src_hash()` (translatable-leaf model).
- `backend/auth_service/services/content_locale.py` — pure: `pick_locale_entry()` (resolve per-locale embed row + default fallback).
- `backend/auth_service/translation/__init__.py` — `get_provider()` selector.
- `backend/auth_service/translation/provider.py` — `TranslationProvider` Protocol.
- `backend/auth_service/translation/null.py` — `NullProvider` (echo).
- `backend/auth_service/tests/test_segments.py`
- `backend/auth_service/tests/test_translation_provider.py`
- `backend/auth_service/tests/test_content_locale.py`
- `backend/auth_service/tests/test_workspace_locale.py`

**Modify:**
- `backend/auth_service/routers/deps.py` — `require_project_access` select gains `default_locale, locales`.
- `backend/auth_service/routers/workspace.py` — `_flatten_service` locale-aware; `list_services`/`get_service` accept `?locale=`; `save_service` writes the right locale row under the new constraint; `add_service` seeds the default-locale row.
- `backend/auth_service/routers/publish.py` — publish updates by row `id` (not `project_service_id`) so it never clobbers sibling locales.
- `backend/auth_service/routers/content.py` — public reads resolve the default-locale row via `pick_locale_entry`.
- `backend/auth_service/tests/test_publish.py` — existing publish test gains `id`/`locale` on its rows; new no-clobber regression test.

---

## Task 1: Database migration — locale dimension + uniqueness swap

**Files:**
- Create: `backend/migrations/2026_06_05_content_locale.sql`

- [ ] **Step 1: Write the migration file**

```sql
-- CMS multi-language Phase 1: add a per-locale dimension to content.
-- Behavior-preserving: existing single-locale content is tagged with each
-- project's default locale; the one-row-per-service uniqueness becomes
-- one-row-per-(service, locale).

-- 1. Per-project locale configuration.
ALTER TABLE projects
    ADD COLUMN IF NOT EXISTS default_locale text NOT NULL DEFAULT 'en',
    ADD COLUMN IF NOT EXISTS locales        text[] NOT NULL DEFAULT '{}';

COMMENT ON COLUMN projects.default_locale IS
    'The language the client authors in; the source for auto-translation.';
COMMENT ON COLUMN projects.locales IS
    'All locales this project publishes; default_locale listed first.';

-- 2. content_entries locale dimension + per-leaf override tracking.
ALTER TABLE content_entries
    ADD COLUMN IF NOT EXISTS locale           text,
    ADD COLUMN IF NOT EXISTS translation_meta jsonb NOT NULL DEFAULT '{}'::jsonb;

COMMENT ON COLUMN content_entries.locale IS
    'ISO-639/BCP-47 locale code for this content row. One row per (service, locale).';
COMMENT ON COLUMN content_entries.translation_meta IS
    'Per-leaf override tracking: { "<leaf-path>": { "src_hash": "..." } }. Only manually-overridden leaves appear.';

-- 3. Backfill existing rows to their project's default locale.
UPDATE content_entries ce
SET locale = p.default_locale
FROM project_services ps
JOIN projects p ON p.id = ps.project_id
WHERE ce.project_service_id = ps.id
  AND ce.locale IS NULL;

-- 4. Initialise projects.locales = [default_locale] where still empty.
UPDATE projects
SET locales = ARRAY[default_locale]
WHERE cardinality(locales) = 0;

-- 5. Enforce NOT NULL now that every row is backfilled.
ALTER TABLE content_entries ALTER COLUMN locale SET NOT NULL;

-- 6. Swap the one-to-one uniqueness for per-(service, locale) uniqueness.
--    Drop whatever the existing UNIQUE(project_service_id) constraint is named.
DO $$
DECLARE conname text;
BEGIN
    SELECT con.conname INTO conname
    FROM pg_constraint con
    JOIN pg_class rel ON rel.oid = con.conrelid
    WHERE rel.relname = 'content_entries'
      AND con.contype = 'u'
      AND con.conkey = (
          SELECT array_agg(att.attnum)
          FROM pg_attribute att
          WHERE att.attrelid = rel.oid AND att.attname = 'project_service_id'
      );
    IF conname IS NOT NULL THEN
        EXECUTE format('ALTER TABLE content_entries DROP CONSTRAINT %I', conname);
    END IF;
END $$;

ALTER TABLE content_entries
    ADD CONSTRAINT content_entries_service_locale_key UNIQUE (project_service_id, locale);
```

- [ ] **Step 2: Apply via Supabase MCP**

Apply the file with the Supabase MCP `apply_migration` tool: name `content_locale`, body = the SQL above. Do not run psql.
Expected: success, no error.

- [ ] **Step 3: Verify schema with the Supabase MCP**

Run (via MCP `execute_sql`):

```sql
SELECT column_name FROM information_schema.columns
WHERE table_name IN ('projects','content_entries')
  AND column_name IN ('default_locale','locales','locale','translation_meta')
ORDER BY column_name;
```
Expected rows: `default_locale`, `locale`, `locales`, `translation_meta`.

Then confirm the new uniqueness and a clean backfill:

```sql
SELECT conname FROM pg_constraint WHERE conname = 'content_entries_service_locale_key';
SELECT count(*) AS null_locales FROM content_entries WHERE locale IS NULL;
```
Expected: one constraint row; `null_locales = 0`.

- [ ] **Step 4: Commit**

```bash
git add backend/migrations/2026_06_05_content_locale.sql
git commit -m "feat(cms): add per-locale dimension to content_entries + projects"
```

---

## Task 2: Translatable-segment model (`segments.py`)

**Files:**
- Create: `backend/auth_service/services/segments.py`
- Test: `backend/auth_service/tests/test_segments.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_segments.py
from auth_service.services.segments import segments_of, src_hash


def test_src_hash_is_stable_and_changes_with_input():
    assert src_hash("hello") == src_hash("hello")
    assert src_hash("hello") != src_hash("hellp")
    assert len(src_hash("hello")) == 16


def test_text_block_yields_title_and_body():
    out = segments_of("text_block", {"title": "Hi", "body": "Body **md**"})
    assert out == {"title": "Hi", "body": "Body **md**"}


def test_text_block_skips_empty_and_missing():
    assert segments_of("text_block", {"title": "", "body": "Only body"}) == {"body": "Only body"}
    assert segments_of("text_block", {}) == {}


def test_image_yields_alt_only():
    out = segments_of("image", {"url": "/logo.png", "alt": "Company logo"})
    assert out == {"alt": "Company logo"}


def test_file_download_yields_filename_only():
    out = segments_of("file_download", {"url": "/x.pdf", "filename": "Brochure"})
    assert out == {"filename": "Brochure"}


def test_key_value_yields_string_values_only():
    out = segments_of(
        "key_value",
        {"entries": {"email": "a@b.com", "program": "Mon-Fri", "count": 3}},
    )
    assert out == {"entries.email": "a@b.com", "entries.program": "Mon-Fri"}


def test_repeater_uses_item_id_and_field_types():
    content = {
        "_schema": [
            {"key": "title", "type": "string"},
            {"key": "desc", "type": "richtext"},
            {"key": "link", "type": "url"},
            {"key": "tags", "type": "tags"},
        ],
        "items": [
            {"_id": "abc", "title": "Hosting", "desc": "Fast", "link": "/h", "tags": ["a", "b"]},
        ],
    }
    out = segments_of("repeater", content)
    assert out == {
        "items.abc.title": "Hosting",
        "items.abc.desc": "Fast",
        "items.abc.tags.0": "a",
        "items.abc.tags.1": "b",
    }  # url field excluded; tags exploded per element


def test_repeater_falls_back_to_index_without_id():
    content = {"_schema": [{"key": "title", "type": "string"}], "items": [{"title": "X"}]}
    assert segments_of("repeater", content) == {"items.0.title": "X"}


def test_non_text_types_yield_nothing():
    assert segments_of("gallery", {"items": ["/a.jpg", "/b.jpg"]}) == {}
    assert segments_of("video", {"url": "/v", "poster": "/p"}) == {}
    assert segments_of("email_config", {"destination_email": "x@y.com"}) == {}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_segments.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.segments'`.

- [ ] **Step 3: Implement `segments.py`**

```python
# backend/auth_service/services/segments.py
"""Translatable-segment model for CMS content.

Flattens a service's content blob into a flat map of {leaf_path: text} for the
leaves that are human-readable and worth translating, driven by service type and
(for repeaters) the per-item field schema. URLs, emails, numbers and image
sources are never translated.

Used by the multilingual pipeline to (a) auto-translate the default locale into
others and (b) track which leaves a client manually overrode. Pure — no I/O.
"""
from __future__ import annotations

import hashlib

# Repeater field types whose values are translatable text.
_TRANSLATABLE_FIELD_TYPES = {"string", "richtext", "tags"}


def src_hash(text: str) -> str:
    """Stable 16-hex-char fingerprint of a source string, used to detect when a
    default-locale source changed since a translation/override was anchored."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def segments_of(service_type: str, content: dict) -> dict[str, str]:
    """Return {leaf_path: text} for the translatable leaves of one service.

    Leaf paths are dot-delimited and stable: e.g. "title", "entries.email",
    "items.<id>.short_description", "items.<id>.features.0". Repeater items are
    keyed by their stable "_id" when present, else by positional index.
    """
    if not isinstance(content, dict):
        return {}

    out: dict[str, str] = {}

    if service_type == "text_block":
        for key in ("title", "body"):
            val = content.get(key)
            if isinstance(val, str) and val:
                out[key] = val

    elif service_type in ("image", "floor_plan"):
        val = content.get("alt")
        if isinstance(val, str) and val:
            out["alt"] = val

    elif service_type == "file_download":
        val = content.get("filename")
        if isinstance(val, str) and val:
            out["filename"] = val

    elif service_type == "key_value":
        entries = content.get("entries")
        if isinstance(entries, dict):
            for key, val in entries.items():
                if isinstance(val, str) and val:
                    out[f"entries.{key}"] = val

    elif service_type == "repeater":
        schema = {
            field["key"]: field.get("type")
            for field in (content.get("_schema") or [])
            if isinstance(field, dict) and "key" in field
        }
        for idx, item in enumerate(content.get("items") or []):
            if not isinstance(item, dict):
                continue
            item_id = item.get("_id") or str(idx)
            for key, ftype in schema.items():
                if ftype not in _TRANSLATABLE_FIELD_TYPES:
                    continue
                val = item.get(key)
                if ftype == "tags" and isinstance(val, list):
                    for j, tag in enumerate(val):
                        if isinstance(tag, str) and tag:
                            out[f"items.{item_id}.{key}.{j}"] = tag
                elif isinstance(val, str) and val:
                    out[f"items.{item_id}.{key}"] = val

    # gallery (URLs), video (URLs), email_config (private): no translatable text.
    return out
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest auth_service/tests/test_segments.py -v`
Expected: PASS (9 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/segments.py backend/auth_service/tests/test_segments.py
git commit -m "feat(cms): add translatable-segment model + src_hash"
```

---

## Task 3: Translation provider scaffold (`translation/`)

**Files:**
- Create: `backend/auth_service/translation/__init__.py`, `backend/auth_service/translation/provider.py`, `backend/auth_service/translation/null.py`
- Test: `backend/auth_service/tests/test_translation_provider.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_translation_provider.py
import pytest

from auth_service.translation import NullProvider, get_provider


def test_null_provider_echoes_input():
    p = NullProvider()
    assert p.name == "null"
    assert p.translate(["a", "b"], source="en", target="nl") == ["a", "b"]


def test_get_provider_defaults_to_null(monkeypatch):
    monkeypatch.delenv("TRANSLATION_PROVIDER", raising=False)
    assert get_provider().name == "null"


def test_get_provider_explicit_null():
    assert get_provider("null").name == "null"


def test_get_provider_reads_env(monkeypatch):
    monkeypatch.setenv("TRANSLATION_PROVIDER", "null")
    assert get_provider().name == "null"


def test_get_provider_unknown_raises():
    with pytest.raises(ValueError):
        get_provider("does-not-exist")
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.translation'`.

- [ ] **Step 3: Implement the three module files**

```python
# backend/auth_service/translation/provider.py
"""Provider interface for machine translation. Implementations preserve ICU
placeholders (e.g. {year}) and any markup indicated by `fmt`, and return a list
whose order matches the input."""
from __future__ import annotations

from typing import Literal, Protocol, runtime_checkable

TextFormat = Literal["text", "markdown", "html"]


@runtime_checkable
class TranslationProvider(Protocol):
    name: str

    def translate(
        self, texts: list[str], *, source: str, target: str, fmt: TextFormat = "text"
    ) -> list[str]: ...
```

```python
# backend/auth_service/translation/null.py
"""No-op provider: echoes source text unchanged. Used for manual-only projects
and as the safe default before a real engine (DeepL, added in Phase 2) is
configured — lets the whole pipeline run with no external dependency."""
from __future__ import annotations

from .provider import TextFormat


class NullProvider:
    name = "null"

    def translate(
        self, texts: list[str], *, source: str, target: str, fmt: TextFormat = "text"
    ) -> list[str]:
        return list(texts)
```

```python
# backend/auth_service/translation/__init__.py
"""Translation provider registry. DeepLProvider is registered in Phase 2."""
from __future__ import annotations

import os

from .null import NullProvider
from .provider import TranslationProvider

_PROVIDERS = {
    "null": NullProvider,
}


def get_provider(name: str | None = None) -> TranslationProvider:
    """Return the configured provider. Resolution: explicit `name` →
    env TRANSLATION_PROVIDER → "null". Raises ValueError for an unknown name."""
    key = (name or os.environ.get("TRANSLATION_PROVIDER") or "null").lower()
    try:
        return _PROVIDERS[key]()
    except KeyError as exc:
        raise ValueError(f"Unknown translation provider: {key!r}") from exc


__all__ = ["TranslationProvider", "NullProvider", "get_provider"]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest auth_service/tests/test_translation_provider.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/translation backend/auth_service/tests/test_translation_provider.py
git commit -m "feat(cms): scaffold pluggable translation provider interface + NullProvider"
```

---

## Task 4: Per-locale embed resolver (`content_locale.py`)

**Files:**
- Create: `backend/auth_service/services/content_locale.py`
- Test: `backend/auth_service/tests/test_content_locale.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_content_locale.py
from auth_service.services.content_locale import pick_locale_entry


def _row(locale, title):
    return {"locale": locale, "draft_content": {"title": title}, "published_content": None}


def test_picks_requested_locale_from_list():
    rows = [_row("en", "EN"), _row("nl", "NL")]
    assert pick_locale_entry(rows, "nl", "en")["draft_content"]["title"] == "NL"


def test_falls_back_to_default_when_locale_missing():
    rows = [_row("en", "EN")]
    assert pick_locale_entry(rows, "nl", "en")["draft_content"]["title"] == "EN"


def test_legacy_dict_embed_returned_as_is():
    legacy = {"draft_content": {"title": "LEGACY"}, "published_content": None}
    assert pick_locale_entry(legacy, "nl", "en")["draft_content"]["title"] == "LEGACY"


def test_none_returns_none():
    assert pick_locale_entry(None, "en", "en") is None


def test_empty_list_returns_none():
    assert pick_locale_entry([], "en", "en") is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_content_locale.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'auth_service.services.content_locale'`.

- [ ] **Step 3: Implement `content_locale.py`**

```python
# backend/auth_service/services/content_locale.py
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
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `cd backend && python -m pytest auth_service/tests/test_content_locale.py -v`
Expected: PASS (5 passed).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/services/content_locale.py backend/auth_service/tests/test_content_locale.py
git commit -m "feat(cms): add per-locale content_entries embed resolver"
```

---

## Task 5: Locale-aware workspace reads

Make `require_project_access` surface the project's locale config, and make the workspace read endpoints select a locale (defaulting to the project default) via `pick_locale_entry`.

**Files:**
- Modify: `backend/auth_service/routers/deps.py:24-28` (select columns)
- Modify: `backend/auth_service/routers/workspace.py:82-117` (`_flatten_service`), `:123-166` (`list_services`, `get_service`)
- Test: `backend/auth_service/tests/test_workspace_locale.py`

- [ ] **Step 1: Write the failing tests**

```python
# backend/auth_service/tests/test_workspace_locale.py
from unittest.mock import MagicMock


def _svc_with_locale_rows():
    return {
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": [
            {"locale": "en", "draft_content": {"title": "EN"}, "published_content": None,
             "updated_at": "2026-06-05T10:00:00Z"},
            {"locale": "nl", "draft_content": {"title": "NL"}, "published_content": None,
             "updated_at": "2026-06-05T10:00:00Z"},
        ],
    }


def test_get_service_defaults_to_project_default_locale(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)  # faked project has no default_locale → falls back to "en"
    mock_supabase.execute.return_value = MagicMock(data=_svc_with_locale_rows())

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "EN"


def test_get_service_honors_locale_query_param(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(data=_svc_with_locale_rows())

    res = client.get("/projects/demo/services/hero?locale=nl")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "NL"


def test_get_service_falls_back_to_default_when_locale_absent(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(data=_svc_with_locale_rows())

    res = client.get("/projects/demo/services/hero?locale=fr")  # fr has no row
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "EN"  # default-locale fallback
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_locale.py -v`
Expected: FAIL — `?locale=nl` returns "EN" (current `_flatten_service` picks `raw[0]` = the EN row regardless), and the `?locale=` param isn't accepted.

- [ ] **Step 3: Update `require_project_access` select (`deps.py`)**

Replace the `.select(...)` argument at `deps.py:26-28`:

```python
        .select(
            "id, name, slug, user_id, is_active, github_repo, preview_url, production_url, production_branch, repo_branch, default_locale, locales"
        )
```

- [ ] **Step 4: Make `_flatten_service` locale-aware (`workspace.py`)**

Add the import near the other service imports at the top of `workspace.py`:

```python
from ..services.content_locale import pick_locale_entry
```

Replace `_flatten_service` (`workspace.py:82-117`) with:

```python
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
```

- [ ] **Step 5: Thread locale through `list_services` and `get_service` (`workspace.py`)**

Replace `list_services` (`workspace.py:123-144`) with:

```python
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
        logger.exception("list_services failed for project %s: %s", project_slug, exc)
        raise HTTPException(status_code=500, detail="Failed to list services") from exc
```

Replace `get_service` (`workspace.py:147-166`) with:

```python
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
            "id, service_key, label, display_order, page_name, service_type_slug, service_types(name, icon, schema), content_entries(locale, draft_content, published_content, updated_at)"
        )
        .eq("project_id", project["id"])
        .eq("service_key", service_key)
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Service not found")

    return _flatten_service(result.data, loc, default_locale)
```

- [ ] **Step 6: Run the new tests + the existing workspace tests**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_locale.py auth_service/tests/test_workspace_save.py -v`
Expected: PASS. (Existing `test_workspace_save.py` still passes: its `content_entries` is a legacy dict, which `pick_locale_entry` returns as-is.)

- [ ] **Step 7: Commit**

```bash
git add backend/auth_service/routers/deps.py backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_locale.py
git commit -m "feat(cms): locale-aware workspace reads (default-locale fallback)"
```

---

## Task 6: Locale-aware workspace writes

`save_service` must write to the correct `(project_service_id, locale)` row under the new constraint; `add_service` must stamp the seeded repeater row with the default locale. Phase 1 writes only the default-locale row (no other-locale rows yet).

**Files:**
- Modify: `backend/auth_service/routers/workspace.py:169-218` (`save_service`), `:366-374` (`add_service` seed)
- Test: `backend/auth_service/tests/test_workspace_locale.py` (extend)

- [ ] **Step 1: Add the failing tests (append to `test_workspace_locale.py`)**

```python
def test_save_service_writes_locale_and_correct_conflict_target(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)
    mock_supabase.execute.side_effect = [
        # resolve project_service
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}}}),
        # upsert
        MagicMock(data=[{"id": "svc-1"}]),
        # get_service re-fetch
        MagicMock(data={"id": "svc-1", "service_key": "hero", "label": "Hero",
                        "display_order": 1, "page_name": "General",
                        "service_type_slug": "text_block",
                        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
                        "content_entries": [{"locale": "en", "draft_content": {"title": "NEW"},
                                             "published_content": None,
                                             "updated_at": "2026-06-05T10:00:00Z"}]}),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "NEW"}})
    assert res.status_code == 200

    payload = [
        c.args[0] for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ][0]
    assert payload["locale"] == "en"  # faked project default
    # on_conflict must target the composite key, not project_service_id alone
    upsert_kwargs = mock_supabase.upsert.call_args_list[0].kwargs
    assert upsert_kwargs.get("on_conflict") == "project_service_id,locale"
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_locale.py::test_save_service_writes_locale_and_correct_conflict_target -v`
Expected: FAIL — payload has no `locale` key and `on_conflict` is `"project_service_id"`.

- [ ] **Step 3: Update `save_service` (`workspace.py:169-218`)**

Replace the signature and the upsert block with:

```python
@router.put("/projects/{project_slug}/services/{service_key}", response_model=ServiceDetailOut)
async def save_service(
    project_slug: str,
    service_key: str,
    body: ContentSaveRequest,
    request: Request,
    seed: bool = False,
    locale: str | None = None,
):
    user = await require_user(request)
    if seed and not user.is_admin:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN, detail="seed=true requires admin"
        )
    project = require_project_access(project_slug, user)
    default_locale = project.get("default_locale") or "en"
    loc = locale or default_locale

    sb = get_supabase_admin()

    # Resolve the project_service id
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
    now = datetime.now(UTC).isoformat()

    # Upsert the draft for THIS locale only. The composite (project_service_id,
    # locale) conflict target keeps sibling locales untouched. seed=true (admin /
    # agent provisioning) also seeds published_content for a first publish.
    payload: dict = {
        "project_service_id": svc_id,
        "locale": loc,
        "draft_content": body.content,
        "updated_at": now,
        "updated_by": user.id,
    }
    if seed:
        payload["published_content"] = body.content

    sb.table("content_entries").upsert(
        payload, on_conflict="project_service_id,locale"
    ).execute()

    # Return fresh state for the same locale
    return await get_service(project_slug, service_key, request, locale=loc)
```

- [ ] **Step 4: Update `add_service` repeater seed (`workspace.py:366-374`)**

Replace the seed insert block with (adds `"locale"`):

```python
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
```

- [ ] **Step 5: Run the new test + the existing save/seed tests**

Run: `cd backend && python -m pytest auth_service/tests/test_workspace_locale.py auth_service/tests/test_workspace_save.py -v`
Expected: PASS. (`test_put_service_writes_to_draft_content_only` and `test_put_service_with_seed_true_writes_both_columns` still pass — the payload simply gains a `locale` key.)

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/workspace.py backend/auth_service/tests/test_workspace_locale.py
git commit -m "feat(cms): locale-aware workspace writes under composite uniqueness"
```

---

## Task 7: Per-locale-safe publish

Under the new constraint a service has several `content_entries` rows. Publishing must update each row by its own `id` — updating by `project_service_id` would overwrite every locale with one locale's draft.

**Files:**
- Modify: `backend/auth_service/routers/publish.py:36-58` (publish select + per-row update)
- Test: `backend/auth_service/tests/test_publish.py` (update existing rows + add no-clobber regression)

- [ ] **Step 1: Update the existing publish test's mock rows + add the regression test (`test_publish.py`)**

In `test_publish_copies_draft_to_published_and_bumps_timestamp`, change the second `MagicMock(data=[...])` (the "entries that differ" fetch) so each entry carries an `id` and a `locale`:

```python
        # Fetch entries that differ (our "needs publish" query)
        MagicMock(
            data=[
                {
                    "id": "ce-1",
                    "project_service_id": "svc-1",
                    "locale": "en",
                    "draft_content": {"title": "A"},
                    "published_content": {"title": "OLD_A"},
                },
                {
                    "id": "ce-2",
                    "project_service_id": "svc-2",
                    "locale": "en",
                    "draft_content": {"title": "B"},
                    "published_content": {"title": "OLD_B"},
                },
            ]
        ),
```

Append a new regression test that proves two locales of the SAME service publish independently:

```python
def test_publish_updates_each_locale_row_independently(mock_supabase, client, auth_as, client_user):
    """Two locale rows share one project_service_id. Publish must update each by
    its own id, never clobber a sibling locale by writing on project_service_id."""
    auth_as(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(
            data=[
                {"id": "ce-en", "project_service_id": "svc-1", "locale": "en",
                 "draft_content": {"title": "EN-new"}, "published_content": {"title": "EN-old"}},
                {"id": "ce-nl", "project_service_id": "svc-1", "locale": "nl",
                 "draft_content": {"title": "NL-new"}, "published_content": {"title": "NL-old"}},
            ]
        ),
        MagicMock(data=[{"id": "ce-en"}]),
        MagicMock(data=[{"id": "ce-nl"}]),
        MagicMock(data=[{"last_published_at": "2026-06-05T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")
    assert res.status_code == 200
    assert res.json()["published_count"] == 2

    # Every content_entries update must be keyed on the row id, not project_service_id.
    eq_keys = [c.args[0] for c in mock_supabase.eq.call_args_list]
    assert "id" in eq_keys  # update path used .eq("id", ...)
    assert "ce-en" in [c.args[1] for c in mock_supabase.eq.call_args_list if c.args[0] == "id"]
    assert "ce-nl" in [c.args[1] for c in mock_supabase.eq.call_args_list if c.args[0] == "id"]
```

- [ ] **Step 2: Run to verify the new regression test fails**

Run: `cd backend && python -m pytest auth_service/tests/test_publish.py::test_publish_updates_each_locale_row_independently -v`
Expected: FAIL — current code calls `.eq("project_service_id", ...)`, so no `.eq("id", ...)` is recorded (and it would clobber the sibling locale in reality).

- [ ] **Step 3: Update `publish_project` (`publish.py:36-58`)**

Replace the entries fetch + update loop with:

```python
    entries_result = (
        sb.table("content_entries")
        .select("id, project_service_id, locale, draft_content, published_content")
        .in_("project_service_id", svc_ids)
        .execute()
    )

    to_publish = [
        e
        for e in (entries_result.data or [])
        if e.get("draft_content") != e.get("published_content")
    ]

    # Per-row update keyed on the row id — never on project_service_id, which
    # would overwrite every locale of the service with one locale's draft.
    now = datetime.now(UTC).isoformat()
    for entry in to_publish:
        sb.table("content_entries").update(
            {
                "published_content": entry["draft_content"],
                "updated_at": now,
            }
        ).eq("id", entry["id"]).execute()
```

- [ ] **Step 4: Run the publish tests**

Run: `cd backend && python -m pytest auth_service/tests/test_publish.py -v`
Expected: PASS (all, including the updated copy test and the new no-clobber regression).

- [ ] **Step 5: Commit**

```bash
git add backend/auth_service/routers/publish.py backend/auth_service/tests/test_publish.py
git commit -m "fix(cms): publish per content_entries row id to protect sibling locales"
```

---

## Task 8: Locale-aware public content reads

Make the public read endpoints resolve the project's default-locale row (legacy `GET /content/{slug}` behavior is preserved — it returns the default locale, which in Phase 1 is the only locale present).

**Files:**
- Modify: `backend/auth_service/routers/content.py:8` (import), `:28-51` (`_resolve_project`, drop `_resolve_content_entry`), `:84-122` and `:168-207` (both read loops)
- Test: `backend/auth_service/tests/test_content.py` (add locale tests; existing tests stay green)

- [ ] **Step 1: Add the failing tests (append to `test_content.py`)**

```python
def test_public_content_returns_default_locale_row(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True,
                        "default_locale": "nl", "locales": ["nl", "en"]}),
        MagicMock(
            data=[
                {
                    "service_key": "hero",
                    "label": "Hero",
                    "display_order": 1,
                    "service_type_slug": "text_block",
                    "content_entries": [
                        {"locale": "nl", "published_content": {"title": "NL"},
                         "draft_content": {"title": "NL-d"}, "updated_at": "2026-06-05T10:00:00Z"},
                        {"locale": "en", "published_content": {"title": "EN"},
                         "draft_content": {"title": "EN-d"}, "updated_at": "2026-06-05T10:00:00Z"},
                    ],
                },
            ]
        ),
    ]

    res = client.get("/content/demo")
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "NL"  # project default_locale = nl
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd backend && python -m pytest auth_service/tests/test_content.py::test_public_content_returns_default_locale_row -v`
Expected: FAIL — current `_resolve_content_entry` returns `raw[0]` (the NL row here by luck) but does not honor `default_locale`, and `_resolve_project` doesn't select `default_locale` so the value isn't available; with an `[en, nl]` ordering the wrong row would win.

- [ ] **Step 3: Update the import + `_resolve_project` (`content.py`)**

Change the import line `content.py:8` to add the resolver:

```python
from ..services.content_locale import pick_locale_entry
from ..services.supabase_client import get_supabase_admin
```

Update `_resolve_project` (`content.py:28-40`) select to include locale config:

```python
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
```

Delete the `_resolve_content_entry` function (`content.py:43-51`) — it is replaced by `pick_locale_entry`.

- [ ] **Step 4: Update both read loops (`content.py`)**

In `get_project_content`, change the embed select and entry resolution. The select string at `content.py:91-93` becomes:

```python
            "service_key, label, display_order, service_type_slug, content_entries(locale, published_content, draft_content, updated_at)"
```

Immediately after `project = _resolve_project(project_slug)` add:

```python
    default_locale = project.get("default_locale") or "en"
```

and replace `entry = _resolve_content_entry(svc)` (`content.py:106`) with:

```python
        entry = pick_locale_entry(svc.get("content_entries"), default_locale, default_locale)
```

Apply the identical three changes in `get_project_draft_content`: the same embed select string (`content.py:171-173`), `default_locale = project.get("default_locale") or "en"` after the token check, and replace `entry = _resolve_content_entry(svc)` (`content.py:186`) with the same `pick_locale_entry(...)` call.

- [ ] **Step 5: Run the content tests**

Run: `cd backend && python -m pytest auth_service/tests/test_content.py -v`
Expected: PASS. The new test passes; all existing tests pass because their `content_entries` is a legacy dict that `pick_locale_entry` returns as-is (back-compat branch).

- [ ] **Step 6: Commit**

```bash
git add backend/auth_service/routers/content.py backend/auth_service/tests/test_content.py
git commit -m "feat(cms): public content reads resolve the project default locale"
```

---

## Final verification

- [ ] **Step 1: Run the entire backend suite**

Run: `make test-backend`
Expected: PASS — no regressions. Confirms the migration-shaped reads/writes, the new pure libs, and the publish fix all integrate.

- [ ] **Step 2: Sanity-check a live project via the Supabase MCP**

Run (MCP `execute_sql`), substituting a real slug (e.g. `it-global-services`):

```sql
SELECT p.slug, p.default_locale, p.locales,
       count(ce.*) AS entries, count(DISTINCT ce.locale) AS locales_present
FROM projects p
JOIN project_services ps ON ps.project_id = p.id
JOIN content_entries ce ON ce.project_service_id = ps.id
GROUP BY p.slug, p.default_locale, p.locales;
```
Expected: each project shows `locales_present = 1` and `default_locale` matching its content language (set `it-global-services.default_locale = 'ro'` via MCP `execute_sql` if it backfilled to `'en'`, since its content is Romanian).

- [ ] **Step 3: Confirm `GET /content/{slug}` is unchanged for a live site**

After the backend is deployed, fetch `GET /content/it-global-services` and diff the JSON against a pre-Phase-1 capture. Expected: identical (the default-locale row is the same content that existed before).

---

## Self-review (completed during authoring)

**Spec coverage (Phase 1 slice):** ✅ schema (`projects.default_locale`/`locales`, `content_entries.locale`/`translation_meta`, uniqueness swap, backfill) → Task 1. ✅ segment model + `src_hash` → Task 2. ✅ pluggable provider interface + Null default → Task 3. ✅ per-locale read resolution + default fallback → Task 4. ✅ every read/write path locale-aware while preserving behavior → Tasks 5–8. Deferred to later phases (explicitly out of Phase 1): DeepL provider + auto-translate-on-save + override/stale (Phase 2), new public per-locale endpoints (Phase 2), dashboard locale switcher (Phase 3), client `i18n/request.ts` + i18n-setup skill (Phase 4), connector detect-and-import (Phase 5).

**Placeholder scan:** ✅ no TBD/TODO; every code step shows complete code; every test step shows real assertions; every run step states the expected result.

**Type/name consistency:** ✅ `pick_locale_entry(embedded, locale, default_locale)` signature is identical across Task 4 (definition), Task 5 (`_flatten_service`), and Task 8 (`content.py`). ✅ `_flatten_service(svc, locale, default_locale)` callers (`list_services`, `get_service`, `save_service`→`get_service`) all pass the 3 args. ✅ `segments_of(service_type, content)` / `src_hash(text)` / `get_provider(name=None)` / `NullProvider.name == "null"` used consistently. ✅ `on_conflict="project_service_id,locale"` matches the migration's `content_entries_service_locale_key UNIQUE (project_service_id, locale)`.
