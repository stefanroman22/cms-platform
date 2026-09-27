"""Tests for routers/deps.py — the shared auth/project-access dependencies.

Lives in its own file because the regression below targets deps.py
specifically: router tests stub out require_project_access via the auth_as
fixture so they cannot catch a narrowed SELECT.
"""

from __future__ import annotations


def test_require_project_access_selects_publish_fields(mock_supabase, admin_user):
    """Regression: deps.require_project_access must SELECT production_branch,
    production_url and repo_branch so the publish/connector flows have the
    fields they need."""
    from auth_service.routers import deps

    mock_supabase.execute.return_value.data = {
        "id": "p1",
        "name": "Acme",
        "slug": "acme",
        "user_id": admin_user.id,
        "is_active": True,
        "github_repo": "https://github.com/x/acme",
        "preview_url": "https://acme-dev.vercel.app",
        "production_url": "https://acme.vercel.app",
        "production_branch": "master",
        "repo_branch": "cms-preview",
    }

    project = deps.require_project_access("acme", admin_user)

    select_arg = mock_supabase.select.call_args.args[0]
    assert "production_branch" in select_arg
    assert "production_url" in select_arg
    assert "repo_branch" in select_arg

    assert project["production_branch"] == "master"
    assert project["repo_branch"] == "cms-preview"
