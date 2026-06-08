from unittest.mock import MagicMock


def _project(locales):
    return {
        "id": "project-demo",
        "slug": "demo",
        "name": "Demo",
        "default_locale": locales[0],
        "locales": locales,
        "github_repo": "https://github.com/test/demo",
        "repo_branch": "cms-preview",
        "production_branch": "master",
        "preview_url": "https://demo-dev.vercel.app",
        "production_url": "https://demo.vercel.app",
    }


def _patch_project(monkeypatch, locales):
    monkeypatch.setattr(
        "auth_service.routers.workspace.require_project_access",
        lambda slug, user: _project(locales),
    )


def _upserts(mock_supabase):
    return [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]


def test_editing_default_propagates_to_other_locales(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])  # NullProvider (env unset) echoes
    mock_supabase.execute.side_effect = [
        # resolve service
        MagicMock(
            data={
                "id": "svc-1",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "page_name": "General",
                "service_type_slug": "text_block",
                "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            }
        ),
        # fetch existing rows for this service (none yet)
        MagicMock(data=[]),
        MagicMock(data=[{"id": "ce-en"}]),  # upsert en
        MagicMock(data=[{"id": "ce-nl"}]),  # upsert nl
        # get_service re-fetch
        MagicMock(
            data={
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
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-06-05T10:00:00Z",
                    }
                ],
            }
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})
    assert res.status_code == 200

    ups = _upserts(mock_supabase)
    locales_written = {u["locale"] for u in ups}
    assert locales_written == {"en", "nl"}  # propagated to nl
    nl = next(u for u in ups if u["locale"] == "nl")
    assert nl["draft_content"] == {"title": "Hi"}  # NullProvider echo


def test_manual_override_survives_default_edit(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "svc-1",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "page_name": "General",
                "service_type_slug": "text_block",
                "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            }
        ),
        # existing rows: en draft, nl with a MANUAL override on "title"
        MagicMock(
            data=[
                {
                    "id": "ce-en",
                    "locale": "en",
                    "draft_content": {"title": "Old"},
                    "published_content": None,
                    "translation_meta": {},
                },
                {
                    "id": "ce-nl",
                    "locale": "nl",
                    "draft_content": {"title": "mijn titel"},
                    "published_content": None,
                    "translation_meta": {"title": {"src_hash": "abc1230000000000"}},
                },
            ]
        ),
        MagicMock(data=[{"id": "ce-en"}]),
        MagicMock(data=[{"id": "ce-nl"}]),
        MagicMock(
            data={
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
                        "draft_content": {"title": "New"},
                        "published_content": None,
                        "updated_at": "2026-06-05T10:00:00Z",
                    }
                ],
            }
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "New"}})
    assert res.status_code == 200

    nl = next(u for u in _upserts(mock_supabase) if u["locale"] == "nl")
    assert nl["draft_content"]["title"] == "mijn titel"  # override kept
    assert nl["translation_meta"] == {"title": {"src_hash": "abc1230000000000"}}


def test_editing_nondefault_locale_marks_changed_leaf_manual(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en", "nl"])
    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "svc-1",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "page_name": "General",
                "service_type_slug": "text_block",
                "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            }
        ),
        # rows: en source + nl auto translation
        MagicMock(
            data=[
                {
                    "id": "ce-en",
                    "locale": "en",
                    "draft_content": {"title": "Hi"},
                    "published_content": None,
                    "translation_meta": {},
                },
                {
                    "id": "ce-nl",
                    "locale": "nl",
                    "draft_content": {"title": "Hoi"},
                    "published_content": None,
                    "translation_meta": {},
                },
            ]
        ),
        MagicMock(data=[{"id": "ce-nl"}]),  # upsert nl
        MagicMock(
            data={
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
                        "draft_content": {"title": "Hallo"},
                        "published_content": None,
                        "updated_at": "2026-06-05T10:00:00Z",
                    }
                ],
            }
        ),
    ]

    res = client.put(
        "/projects/demo/services/hero?locale=nl", json={"content": {"title": "Hallo"}}
    )  # user overrides nl title
    assert res.status_code == 200

    nl = next(u for u in _upserts(mock_supabase) if u["locale"] == "nl")
    assert "title" in nl["translation_meta"]  # marked manual
    assert "src_hash" in nl["translation_meta"]["title"]


def test_single_locale_project_does_not_call_provider(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    auth_as(client_user)
    _patch_project(monkeypatch, ["en"])  # single locale → no propagation

    def _boom(*a, **k):
        raise AssertionError("get_provider must not be called for single-locale projects")

    monkeypatch.setattr("auth_service.routers.workspace.get_provider", _boom)

    mock_supabase.execute.side_effect = [
        MagicMock(
            data={
                "id": "svc-1",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "page_name": "General",
                "service_type_slug": "text_block",
                "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            }
        ),
        MagicMock(data=[]),  # existing rows
        MagicMock(data=[{"id": "ce-en"}]),  # upsert en
        MagicMock(
            data={
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
                        "draft_content": {"title": "Hi"},
                        "published_content": None,
                        "updated_at": "2026-06-05T10:00:00Z",
                    }
                ],
            }
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "Hi"}})
    assert res.status_code == 200
    ups = _upserts(mock_supabase)
    assert {u["locale"] for u in ups} == {"en"}  # no propagation
