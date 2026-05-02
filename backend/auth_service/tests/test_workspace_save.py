from unittest.mock import MagicMock


def test_put_service_writes_to_draft_content_only(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    # Sequence: _resolve, upsert, get_service's resolve + fetch
    mock_supabase.execute.side_effect = [
        # svc_result in save_service
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
        # upsert returns
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
                "content_entries": {
                    "published_content": {"title": "OLD"},
                    "draft_content": {"title": "NEW"},
                    "updated_at": "2026-04-16T10:00:00Z",
                },
            }
        ),
    ]

    res = client.put(
        "/projects/demo/services/hero",
        json={"content": {"title": "NEW"}},
    )
    assert res.status_code == 200

    # Find the content_entries upsert (identified by project_service_id key)
    # and assert IT specifically writes draft_content and not published_content.
    content_upserts = [
        c.args[0]
        for c in mock_supabase.upsert.call_args_list
        if isinstance(c.args[0], dict) and "project_service_id" in c.args[0]
    ]
    assert (
        len(content_upserts) == 1
    ), f"expected exactly one content_entries upsert, got {len(content_upserts)}"
    payload = content_upserts[0]
    assert "draft_content" in payload
    assert "published_content" not in payload


def test_get_service_returns_draft_with_fallback_to_published(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            "content_entries": {
                "published_content": {"title": "PUB"},
                "draft_content": {"title": "DRAFT"},
                "updated_at": "2026-04-16T10:00:00Z",
            },
        }
    )

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "DRAFT"


def test_get_service_falls_back_to_published_when_draft_null(
    mock_supabase, client, auth_as, client_user
):
    auth_as(client_user)

    mock_supabase.execute.return_value = MagicMock(
        data={
            "id": "svc-1",
            "service_key": "hero",
            "label": "Hero",
            "display_order": 1,
            "page_name": "General",
            "service_type_slug": "text_block",
            "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
            "content_entries": {
                "published_content": {"title": "PUB"},
                "draft_content": None,
                "updated_at": "2026-04-16T10:00:00Z",
            },
        }
    )

    res = client.get("/projects/demo/services/hero")
    assert res.status_code == 200
    assert res.json()["content"]["title"] == "PUB"


def test_put_service_with_seed_true_writes_both_columns(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)

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
        MagicMock(data=[{"id": "svc-1"}]),
        MagicMock(
            data={
                "id": "svc-1",
                "service_key": "hero",
                "label": "Hero",
                "display_order": 1,
                "page_name": "General",
                "service_type_slug": "text_block",
                "service_types": {"name": "Text block", "icon": "Box", "schema": {}},
                "content_entries": {
                    "published_content": {"title": "X"},
                    "draft_content": {"title": "X"},
                    "updated_at": "2026-04-16T10:00:00Z",
                },
            }
        ),
    ]

    res = client.put(
        "/projects/demo/services/hero?seed=true",
        json={"content": {"title": "X"}},
    )
    assert res.status_code == 200

    payload = mock_supabase.upsert.call_args_list[0].args[0]
    assert payload.get("draft_content") == {"title": "X"}
    assert payload.get("published_content") == {"title": "X"}


def test_put_service_seed_true_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)

    res = client.put(
        "/projects/demo/services/hero?seed=true",
        json={"content": {"title": "X"}},
    )
    assert res.status_code == 403


def test_admin_get_project_returns_vercel_fields(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(
        data={
            "slug": "demo",
            "name": "Demo",
            "github_repo": "x/y",
            "vercel_project_id": "prj_1",
            "production_url": "https://p",
            "preview_url": "https://pr",
            "preview_token": "tok123",
            "last_published_at": None,
        }
    )

    res = client.get("/admin/projects/demo")
    assert res.status_code == 200
    body = res.json()
    assert body["preview_token"] == "tok123"
    assert body["vercel_project_id"] == "prj_1"


def test_admin_get_project_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)
    res = client.get("/admin/projects/demo")
    assert res.status_code == 403


def test_admin_patch_project_updates_vercel_fields(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=[{"slug": "demo"}])

    res = client.patch(
        "/admin/projects/demo",
        json={
            "vercel_project_id": "prj_abc",
            "production_url": "https://x.vercel.app",
            "preview_url": "https://x-preview.vercel.app",
            "preview_token": "tok",
        },
    )
    assert res.status_code == 200

    updated = mock_supabase.update.call_args_list[0].args[0]
    assert updated["vercel_project_id"] == "prj_abc"
    assert updated["production_url"] == "https://x.vercel.app"
    assert updated["preview_url"] == "https://x-preview.vercel.app"
    assert updated["preview_token"] == "tok"


def test_admin_patch_project_requires_admin(mock_supabase, client, auth_as, client_user):
    auth_as(client_user)
    res = client.patch("/admin/projects/demo", json={"preview_token": "x"})
    assert res.status_code == 403
