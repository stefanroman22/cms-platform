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
            {
                "locale": "en",
                "draft_content": {"title": "EN"},
                "published_content": None,
                "updated_at": "2026-06-05T10:00:00Z",
            },
            {
                "locale": "nl",
                "draft_content": {"title": "NL"},
                "published_content": None,
                "updated_at": "2026-06-05T10:00:00Z",
            },
        ],
    }


def test_get_service_defaults_to_project_default_locale(
    mock_supabase, client, auth_as, client_user
):
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


def test_save_service_writes_locale_and_correct_conflict_target(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)
    mock_supabase.execute.side_effect = [
        # resolve project_service
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
        # rows fetch (no existing locale rows)
        MagicMock(data=[]),
        # upsert
        MagicMock(data=[{"id": "svc-1"}]),
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
                        "draft_content": {"title": "NEW"},
                        "published_content": None,
                        "updated_at": "2026-06-05T10:00:00Z",
                    }
                ],
            }
        ),
    ]

    res = client.put("/projects/demo/services/hero", json={"content": {"title": "NEW"}})
    assert res.status_code == 200

    payload = [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ][0]
    assert payload["locale"] == "en"  # faked project default
    # on_conflict must target the composite key, not project_service_id alone
    upsert_kwargs = mock_supabase.upsert.call_args_list[0].kwargs
    assert upsert_kwargs.get("on_conflict") == "project_service_id,locale"
