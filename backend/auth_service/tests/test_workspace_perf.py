"""Performance-shape tests for the dashboard content endpoints: how many
auth/project lookups a request does, parallel translation, and list filtering."""

from unittest.mock import MagicMock

SVC_ROW = {
    "id": "svc-1",
    "service_key": "hero",
    "label": "Hero",
    "display_order": 1,
    "page_name": "General",
    "service_type_slug": "text_block",
    "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
}


def _project(locales):
    return {
        "id": "project-demo",
        "slug": "demo",
        "name": "Demo",
        "user_id": "user-client",
        "default_locale": locales[0],
        "locales": locales,
        "preview_url": None,
        "production_url": None,
        "rich_text_version": 0,
    }


def _detail_row(entries):
    return {**SVC_ROW, "content_entries": entries}


def test_save_checks_project_access_once(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)
    calls = {"n": 0}

    def fake_access(slug, user):
        calls["n"] += 1
        return _project(["en"])

    monkeypatch.setattr("auth_service.routers.workspace.require_project_access", fake_access)
    mock_supabase.execute.side_effect = [
        MagicMock(data=SVC_ROW),  # resolve service
        MagicMock(data=[]),  # existing rows
        MagicMock(data=[{"id": "ce-en"}]),  # upsert en
        MagicMock(  # detail re-read
            data=_detail_row(
                [
                    {
                        "locale": "en",
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T10:00:00Z",
                        "translation_meta": None,
                    }
                ]
            )
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})

    assert res.status_code == 200
    assert calls["n"] == 1
    body = res.json()
    assert body["content"] == {"title": "Hi"}
    assert body["locale"] == "en"
    assert body["last_updated"] == "2026-09-30T10:00:00Z"


def test_get_service_still_returns_detail(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(["en", "nl"]),
    )
    mock_supabase.execute.side_effect = [
        MagicMock(
            data=_detail_row(
                [
                    {
                        "locale": "nl",
                        "draft_content": {"title": "Hoi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T11:00:00Z",
                        "translation_meta": {},
                    },
                    {
                        "locale": "en",
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-09-30T10:00:00Z",
                        "translation_meta": None,
                    },
                ]
            )
        ),
    ]

    res = client.get("/projects/demo/services/hero?locale=nl")

    assert res.status_code == 200
    body = res.json()
    assert body["content"] == {"title": "Hoi"}
    assert body["locale"] == "nl"
    assert body["default_locale"] == "en"
    assert body["locales"] == ["en", "nl"]
    assert body["translation_status"] == {"title": "auto"}
