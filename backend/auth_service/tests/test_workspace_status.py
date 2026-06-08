"""Tests for Phase-3 translation-status surfacing in get_service."""

from unittest.mock import MagicMock

from auth_service.services.segments import src_hash


def _patch_project(monkeypatch, default_locale="en", locales=None):
    """Monkeypatch require_project_access to return a project with locale fields."""
    if locales is None:
        locales = ["en", "nl"]

    def fake_require_project_access(slug, user):
        return {
            "id": f"project-{slug}",
            "slug": slug,
            "name": slug.title(),
            "default_locale": default_locale,
            "locales": locales,
        }

    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        fake_require_project_access,
    )


def _svc_with_meta(en_title="Hello", nl_title="Hallo", translation_meta=None):
    """Build a full service dict with both en and nl content_entries rows."""
    nl_entry = {
        "locale": "nl",
        "draft_content": {"title": nl_title},
        "published_content": None,
        "updated_at": "2026-06-05T10:00:00Z",
        "translation_meta": translation_meta or {},
    }
    return {
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": [
            {
                "locale": "en",
                "draft_content": {"title": en_title},
                "published_content": None,
                "updated_at": "2026-06-05T10:00:00Z",
                "translation_meta": None,
            },
            nl_entry,
        ],
    }


# ── Test 1: default locale → translation_status is None ──────────────────────


def test_default_locale_has_no_translation_status(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])
    mock_supabase.execute.return_value = MagicMock(data=_svc_with_meta())

    res = client.get("/projects/demo/services/hero")  # no ?locale → defaults to "en"
    assert res.status_code == 200
    body = res.json()
    assert body["translation_status"] is None
    assert body["locale"] == "en"
    assert body["default_locale"] == "en"
    assert body["locales"] == ["en", "nl"]


# ── Test 2: non-default locale, no meta entry → "auto" ───────────────────────


def test_non_default_locale_no_meta_is_auto(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])
    mock_supabase.execute.return_value = MagicMock(data=_svc_with_meta(translation_meta={}))

    res = client.get("/projects/demo/services/hero?locale=nl")
    assert res.status_code == 200
    body = res.json()
    assert body["locale"] == "nl"
    assert body["default_locale"] == "en"
    ts = body["translation_status"]
    assert ts is not None
    # "title" exists in the default-locale content, no meta entry → auto
    assert ts["title"] == "auto"


# ── Test 3: meta entry with matching src_hash → "manual" ─────────────────────


def test_non_default_locale_matching_hash_is_manual(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    en_title = "Hello"
    correct_hash = src_hash(en_title)
    meta = {"title": {"src_hash": correct_hash}}

    mock_supabase.execute.return_value = MagicMock(
        data=_svc_with_meta(en_title=en_title, translation_meta=meta)
    )

    res = client.get("/projects/demo/services/hero?locale=nl")
    assert res.status_code == 200
    ts = res.json()["translation_status"]
    assert ts["title"] == "manual"


# ── Test 4: meta entry with mismatched src_hash → "stale" ────────────────────


def test_non_default_locale_stale_hash_is_stale(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    en_title = "Hello updated"  # source has changed since the override was anchored
    old_hash = src_hash("Hello")  # hash was anchored to the old text
    meta = {"title": {"src_hash": old_hash}}

    mock_supabase.execute.return_value = MagicMock(
        data=_svc_with_meta(en_title=en_title, translation_meta=meta)
    )

    res = client.get("/projects/demo/services/hero?locale=nl")
    assert res.status_code == 200
    ts = res.json()["translation_status"]
    assert ts["title"] == "stale"
