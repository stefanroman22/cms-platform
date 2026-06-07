from unittest.mock import MagicMock
from unittest.mock import patch as patch_


def test_publish_copies_draft_to_published_and_bumps_timestamp(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)

    # Supabase mock for the RPC-like execute chain
    mock_supabase.execute.side_effect = [
        # Fetch project_services for this project
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}]),
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
        MagicMock(
            data=[
                # draft == published — nothing to publish
                {
                    "project_service_id": "svc-1",
                    "draft_content": {"title": "same"},
                    "published_content": {"title": "same"},
                },
            ]
        ),
        MagicMock(data=[{"last_published_at": "2026-04-16T10:00:00Z"}]),
    ]

    res = client.post("/projects/demo/publish")

    assert res.status_code == 200
    assert res.json()["published_count"] == 0


def test_status_reports_unpublished_count_and_urls(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    mock_supabase.execute.side_effect = [
        # Fetch project fields
        MagicMock(
            data={
                "id": "project-demo",
                "preview_url": "https://preview.example.com",
                "production_url": "https://prod.example.com",
                "last_published_at": "2026-04-16T10:00:00Z",
            }
        ),
        # Fetch project_services
        MagicMock(data=[{"id": "svc-1"}, {"id": "svc-2"}, {"id": "svc-3"}]),
        # Count entries where draft != published
        MagicMock(
            data=[
                {
                    "project_service_id": "svc-1",
                    "draft_content": {"a": 1},
                    "published_content": {"a": 2},
                },
                {
                    "project_service_id": "svc-2",
                    "draft_content": {"b": 1},
                    "published_content": {"b": 1},
                },  # same
                {
                    "project_service_id": "svc-3",
                    "draft_content": {"c": 1},
                    "published_content": {"c": 2},
                },
            ]
        ),
    ]

    res = client.get("/projects/demo/status")
    assert res.status_code == 200
    body = res.json()
    assert body["unpublished_count"] == 2
    assert body["preview_url"] == "https://preview.example.com"
    assert body["production_url"] == "https://prod.example.com"
    assert body["last_published_at"] == "2026-04-16T10:00:00Z"


def test_rotate_preview_token_regenerates_and_stores(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)

    mock_supabase.execute.side_effect = [
        # Fetch project + vercel_project_id
        MagicMock(data={"id": "project-demo", "vercel_project_id": "prj_123"}),
        # Update row
        MagicMock(data=[{"preview_token": "<new>"}]),
    ]

    # Patch Vercel call to a no-op
    with patch_("auth_service.routers.publish._update_vercel_preview_env_var") as mock_vercel:
        res = client.post("/admin/projects/demo/rotate-preview-token")

    assert res.status_code == 200
    body = res.json()
    assert len(body["preview_token"]) >= 32
    mock_vercel.assert_called_once()


def test_rotate_preview_token_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    res = client.post("/admin/projects/demo/rotate-preview-token")
    assert res.status_code == 403


def test_publish_updates_each_locale_row_independently(mock_supabase, client, auth_as, client_user):
    """Two locale rows share one project_service_id. Publish must update each by
    its own id, never clobber a sibling locale by writing on project_service_id."""
    auth_as(client_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(
            data=[
                {
                    "id": "ce-en",
                    "project_service_id": "svc-1",
                    "locale": "en",
                    "draft_content": {"title": "EN-new"},
                    "published_content": {"title": "EN-old"},
                },
                {
                    "id": "ce-nl",
                    "project_service_id": "svc-1",
                    "locale": "nl",
                    "draft_content": {"title": "NL-new"},
                    "published_content": {"title": "NL-old"},
                },
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
