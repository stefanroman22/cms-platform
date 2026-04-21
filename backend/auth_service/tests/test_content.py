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


def test_draft_endpoint_requires_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}
    )
    res = client.get("/content/demo/draft")
    assert res.status_code == 401


def test_draft_endpoint_rejects_wrong_token(mock_supabase, client):
    mock_supabase.execute.return_value = MagicMock(
        data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}
    )
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "wrong"})
    assert res.status_code == 401


def test_draft_endpoint_returns_draft_with_valid_token(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}),
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
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "DRAFT"
    assert res.headers["cache-control"] == "no-store"


def test_draft_falls_back_to_published_when_draft_null(mock_supabase, client):
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}),
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": None, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    assert res.json()["content"]["hero"]["title"] == "PUB"


def test_draft_empty_dict_does_not_fall_back_to_published(mock_supabase, client):
    """An editor who clears all fields in a draft must see empty preview,
    not the published content — empty-dict is a real draft state, not 'no draft'."""
    mock_supabase.execute.side_effect = [
        MagicMock(data={"id": "p1", "slug": "demo", "name": "Demo", "is_active": True, "preview_token": "secret-token-xyz"}),
        MagicMock(data=[
            {
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "service_type_slug": "text_block",
                "content_entries": {"published_content": {"title": "PUB"}, "draft_content": {}, "updated_at": "2026-04-16T10:00:00Z"},
            },
        ]),
    ]
    res = client.get("/content/demo/draft", headers={"X-CMS-Preview-Token": "secret-token-xyz"})
    assert res.status_code == 200
    hero = res.json()["content"]["hero"]
    assert "title" not in hero  # draft is {} — no title should appear (not PUB's title)
    assert hero["_type"] == "text_block"
