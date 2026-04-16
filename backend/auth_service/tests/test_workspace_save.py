from unittest.mock import MagicMock


def test_put_service_writes_to_draft_content_only(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    # Sequence: _resolve, upsert, get_service's resolve + fetch
    mock_supabase.execute.side_effect = [
        # svc_result in save_service
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        }),
        # upsert returns
        MagicMock(data=[{"id": "svc-1"}]),
        # get_service re-fetch
        MagicMock(data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            "content_entries": {"published_content": {"title": "OLD"}, "draft_content": {"title": "NEW"}, "updated_at": "2026-04-16T10:00:00Z"},
        }),
    ]

    res = client.put(
        "/projects/demo/services/hero",
        json={"content": {"title": "NEW"}},
    )
    assert res.status_code == 200

    # Find the content_entries upsert (identified by project_service_id key)
    # and assert IT specifically writes draft_content and not published_content.
    content_upserts = [
        c.args[0] for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]
    assert len(content_upserts) == 1, f"expected exactly one content_entries upsert, got {len(content_upserts)}"
    payload = content_upserts[0]
    assert "draft_content" in payload
    assert "published_content" not in payload


def test_get_service_returns_draft_with_fallback_to_published(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(data={
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {"title": "DRAFT"}, "updated_at": "2026-04-16T10:00:00Z"},
    })

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "DRAFT"


def test_get_service_falls_back_to_published_when_draft_null(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(data={
        "id": "svc-1",
        "service_key": "hero",
        "label": "Hero",
        "display_order": 1,
        "page_name": "General",
        "service_type_slug": "text_block",
        "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
        "content_entries": {"published_content": {"title": "PUB"}, "draft_content": None, "updated_at": "2026-04-16T10:00:00Z"},
    })

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "PUB"
