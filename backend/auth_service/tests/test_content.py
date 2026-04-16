from unittest.mock import MagicMock


def test_public_content_returns_published_content_only(mock_supabase, client):
    # Arrange — supabase returns one project + two services
    mock_supabase.execute.side_effect = [
        # _resolve_project
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        # services query
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {"title": "DRAFT"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    body = res.json()
    assert body["content"]["hero"]["title"] == "PUB"  # published, not draft


def test_public_content_filters_services_with_null_published(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True}),
        MagicMock(data=[
            {
                "service_key": "published_svc",
                "label": "Has published",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "YES"}, "draft_content": {"title": "D"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
            {
                "service_key": "unpublished_svc",
                "label": "Draft only",
                "display_order": 2,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": None, "draft_content": {"title": "D"}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]

    res = client.get("/content/demo")

    assert res.status_code == 200
    content = res.json()["content"]
    assert "published_svc" in content
    assert "unpublished_svc" not in content
