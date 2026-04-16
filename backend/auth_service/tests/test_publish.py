from unittest.mock import MagicMock


def test_publish_copies_draft_to_published_and_bumps_timestamp(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    # Supabase mock for the RPC-like execute chain
    mock_supabase.execute.side_effect = [
        # Fetch project_services for this project
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}]),
        # Fetch entries that differ (our "needs publish" query)
        MagicMock(data=[
            {"project_service_id": "svc-1", "draft_content": {"title": "A"}, "published_content": {"title": "OLD_A"}},
            {"project_service_id": "svc-2", "draft_content": {"title": "B"}, "published_content": {"title": "OLD_B"}},
        ]),
        # Update entry 1
        MagicMock(data=[{"project_service_id": "svc-1"}]),
        # Update entry 2
        MagicMock(data=[{"project_service_id": "svc-2"}]),
        # Update projects.last_published_at
        MagicMock(data=[{"last_published_at": "2026-04-16T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    body = res.json()
    assert body["published_count"] == 2
    assert body["last_published_at"] is not None


def test_publish_with_no_changes_returns_zero(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(data=[
            # draft == published — nothing to publish
            {"project_service_id": "svc-1", "draft_content": {"title": "same"}, "published_content": {"title": "same"}},
        ]),
        MagicMock(data=[{"last_published_at": "2026-04-16T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    assert res.json()["published_count"] == 0


def test_status_reports_unpublished_count_and_urls(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.side_effect = [
        # Fetch project fields
        MagicMock(data={
            "id": "project-demo",
            "preview_url": "https://preview.example.com",
            "production_url": "https://prod.example.com",
            "last_published_at": "2026-04-16T10:00:00Z",
        }),
        # Fetch project_services
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}, {"id": "svc-3"}]),
        # Count entries where draft != published
        MagicMock(data=[
            {"project_service_id": "svc-1", "draft_content": {"a": 1}, "published_content": {"a": 2}},
            {"project_service_id": "svc-2", "draft_content": {"b": 1}, "published_content": {"b": 1}},  # same
            {"project_service_id": "svc-3", "draft_content": {"c": 1}, "published_content": {"c": 2}},
        ]),
    ]

    res = client.get("/projects/demo/status")
    assert res.status_code == 200
    body = res.json()
    assert body["unpublished_count"] == 2
    assert body["preview_url"] == "https://preview.example.com"
    assert body["production_url"] == "https://prod.example.com"
    assert body["last_published_at"] == "2026-04-16T10:00:00Z"
