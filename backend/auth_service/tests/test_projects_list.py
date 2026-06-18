"""GET /projects ownership scoping.

Admins operationally own every project (require_project_access already grants
them full access), so the dashboard list returns ALL active projects for an
admin — not just rows where user_id == the admin. Non-admins still see only
their own. (Single-owner model: projects.user_id + is_admin; no co-owner table.)
"""

from unittest.mock import MagicMock


def _row(i: str) -> dict:
    return {
        "id": i,
        "name": i,
        "description": None,
        "slug": i,
        "is_active": True,
        "website_url": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-01T00:00:00Z",
    }


def _patch_user(monkeypatch, user):
    async def fake_require_user(request):  # noqa: ARG001
        return user

    monkeypatch.setattr("auth_service.routers.projects._require_user", fake_require_user)


def test_admin_sees_all_projects_unscoped(mock_supabase, client, monkeypatch, admin_user):
    _patch_user(monkeypatch, admin_user)
    mock_supabase.execute.return_value = MagicMock(data=[_row("p1"), _row("p2"), _row("p3")])

    res = client.get("/projects")

    assert res.status_code == 200
    assert len(res.json()) == 3
    # Admin path must NOT constrain by user_id.
    user_id_filters = [
        c for c in mock_supabase.eq.call_args_list if c.args and c.args[0] == "user_id"
    ]
    assert user_id_filters == [], "admin list must not filter by user_id"


def test_non_admin_scoped_to_own_projects(mock_supabase, client, monkeypatch, client_user):
    _patch_user(monkeypatch, client_user)
    mock_supabase.execute.return_value = MagicMock(data=[_row("mine")])

    res = client.get("/projects")

    assert res.status_code == 200
    user_id_filters = [
        c for c in mock_supabase.eq.call_args_list if c.args and c.args[0] == "user_id"
    ]
    assert any(
        c.args[1] == "client-uuid" for c in user_id_filters
    ), "non-admin list must filter by their own user_id"
