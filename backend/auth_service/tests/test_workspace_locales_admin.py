"""Tests for the locale-management endpoints added in Phase 3:
GET  /projects/{slug}/locales
PUT  /projects/{slug}/locales
POST /projects/{slug}/services/{key}/retranslate
"""

from unittest.mock import MagicMock

# ── helpers ───────────────────────────────────────────────────────────────────


def _project(default_locale="en", locales=None):
    if locales is None:
        locales = [default_locale]
    return {
        "id": "project-demo",
        "slug": "demo",
        "name": "Demo",
        "default_locale": default_locale,
        "locales": locales,
        "github_repo": "https://github.com/test/demo",
        "repo_branch": "cms-preview",
        "production_branch": "master",
        "preview_url": "https://demo-dev.vercel.app",
        "production_url": "https://demo.vercel.app",
    }


def _patch_project(monkeypatch, default_locale="en", locales=None):
    proj = _project(default_locale, locales)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: proj,
    )
    return proj


def _svc_detail_response():
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
                "locale": "nl",
                "draft_content": {"title": "NL"},
                "published_content": None,
                "updated_at": "2026-06-06T10:00:00Z",
                "translation_meta": {},
            }
        ],
    }


# ── 1. GET locales ────────────────────────────────────────────────────────────


def test_get_project_locales(mock_supabase, client, auth_as, admin_user, monkeypatch):
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    res = client.get("/projects/demo/locales")
    assert res.status_code == 200
    body = res.json()
    assert body["default_locale"] == "en"
    assert body["locales"] == ["en", "nl"]


# ── 2. PUT locales — adding a locale ─────────────────────────────────────────


def test_put_locales_add_nl(mock_supabase, client, auth_as, admin_user, monkeypatch):
    """Adding nl to a project that only had en:
    - content_entries upsert is called with locale='nl'
    - projects.update is called with the new locales list
    """
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en"])

    # Execute call sequence:
    # 1. project_services select (svc_rows)
    # 2. content_entries select for svc-1 (entries in the add-loop)
    # 3. content_entries upsert for nl
    # 4. projects.update
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1", "service_type_slug": "text_block"}]),  # svc_rows
        MagicMock(  # entries for svc-1
            data=[
                {
                    "locale": "en",
                    "draft_content": {"title": "Hello"},
                    "published_content": None,
                    "translation_meta": {},
                }
            ]
        ),
        MagicMock(data=[{"project_service_id": "svc-1", "locale": "nl"}]),  # upsert nl
        MagicMock(data=[{"id": "project-demo"}]),  # projects.update
    ]

    res = client.put(
        "/projects/demo/locales", json={"default_locale": "en", "locales": ["en", "nl"]}
    )
    assert res.status_code == 200
    body = res.json()
    assert body["default_locale"] == "en"
    assert "nl" in body["locales"]

    # Assert a content_entries upsert happened for locale='nl'
    upsert_payloads = [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and c.args[0].get("locale") == "nl"
    ]
    assert upsert_payloads, "Expected an upsert for locale='nl'"
    assert upsert_payloads[0]["project_service_id"] == "svc-1"

    # Assert projects.update was called with the new locales
    update_calls = mock_supabase.update.call_args_list
    assert update_calls, "Expected projects.update to be called"
    # The last update call should set the new locales
    last_update_payload = update_calls[-1].args[0]
    assert "nl" in last_update_payload["locales"]
    assert last_update_payload["default_locale"] == "en"


# ── 3. PUT locales — removing a locale ───────────────────────────────────────


def test_put_locales_remove_nl(mock_supabase, client, auth_as, admin_user, monkeypatch):
    """Removing nl from ["en","nl"]:
    - content_entries delete is issued filtered to locale='nl'
    - projects.update called with locales=["en"]
    """
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    # Execute sequence:
    # 1. project_services select (svc_rows)
    # 2. content_entries delete (removed, svc_ids non-empty)
    # 3. projects.update
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1", "service_type_slug": "text_block"}]),  # svc_rows
        MagicMock(data=[]),  # delete execute
        MagicMock(data=[{"id": "project-demo"}]),  # projects.update
    ]

    res = client.put("/projects/demo/locales", json={"default_locale": "en", "locales": ["en"]})
    assert res.status_code == 200
    body = res.json()
    assert body["locales"] == ["en"]

    # Assert delete was called (the chain: .delete().in_().in_().execute())
    assert mock_supabase.delete.called, "Expected content_entries.delete to be called"

    # Assert in_ was called with removed locale
    in_calls = mock_supabase.in_.call_args_list
    locale_in_calls = [c for c in in_calls if c.args and c.args[0] == "locale"]
    assert locale_in_calls, "Expected .in_('locale', ...) call"
    assert "nl" in locale_in_calls[0].args[1]

    # Assert projects.update was called with locales=["en"]
    update_calls = mock_supabase.update.call_args_list
    assert update_calls
    last_payload = update_calls[-1].args[0]
    assert last_payload["locales"] == ["en"]


# ── 4. PUT locales — validation: default_locale not in locales ────────────────


def test_put_locales_default_not_in_locales_returns_422(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en"])

    res = client.put(
        "/projects/demo/locales",
        json={"default_locale": "fr", "locales": ["en", "nl"]},
    )
    assert res.status_code == 422


# ── 5. POST retranslate ───────────────────────────────────────────────────────


def test_retranslate_service_nl(mock_supabase, client, auth_as, admin_user, monkeypatch):
    """POST /retranslate?locale=nl should upsert a fresh nl draft and return 200."""
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    # Execute sequence:
    # 1. project_services single (svc)
    # 2. content_entries select (entries)
    # 3. content_entries upsert (nl)
    # 4. get_service re-fetch (project_services single in get_service)
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "svc-1", "service_type_slug": "text_block"}),  # svc single
        MagicMock(  # entries
            data=[
                {
                    "locale": "en",
                    "draft_content": {"title": "Hello"},
                    "published_content": None,
                }
            ]
        ),
        MagicMock(data=[{"project_service_id": "svc-1", "locale": "nl"}]),  # upsert
        MagicMock(data=_svc_detail_response()),  # get_service re-fetch
    ]

    res = client.post("/projects/demo/services/hero/retranslate?locale=nl")
    assert res.status_code == 200

    # Assert upsert was called for locale='nl'
    upsert_payloads = [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and c.args[0].get("locale") == "nl"
    ]
    assert upsert_payloads, "Expected upsert for locale='nl'"
    assert upsert_payloads[0]["project_service_id"] == "svc-1"
    # NullProvider echoes default content
    assert upsert_payloads[0]["draft_content"] == {"title": "Hello"}


def test_retranslate_service_default_locale_returns_400(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    """Retranslating the default locale (en) must return 400."""
    auth_as(admin_user)
    _patch_project(monkeypatch, default_locale="en", locales=["en", "nl"])

    res = client.post("/projects/demo/services/hero/retranslate?locale=en")
    assert res.status_code == 400
