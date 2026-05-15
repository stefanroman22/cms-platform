"""Tests for routers/deps.py — the shared auth/project-access dependencies.

Lives in its own file (rather than piggybacking on test_issues_router.py)
because the regression below targets deps.py specifically, and the existing
issues-router tests stub out require_project_access via the auth_as fixture
so they cannot catch a narrowed SELECT.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from ..models.schemas import UserOut


def _build_chained_mock(returned_data: dict) -> MagicMock:
    """Build a Supabase-py-style chained MagicMock.

    Every builder method returns the same mock so call args are introspectable
    after the chain resolves, and .execute() returns a result with `.data`.
    """
    mock = MagicMock()
    for method in [
        "table",
        "select",
        "eq",
        "maybe_single",
        "single",
    ]:
        getattr(mock, method).return_value = mock
    mock.execute.return_value = MagicMock(data=returned_data)
    return mock


def test_require_project_access_selects_slack_fields(monkeypatch):
    """Regression: deps.require_project_access must SELECT the fields the Slack
    notification payload reads (github_repo, preview_url). Catches the case
    where slack_notify.py is wired correctly but the project dict is starved
    of context columns — which would surface in production as
    `(repo not set)` / `_(preview not configured)_` placeholders in messages.
    """
    from ..routers import deps

    admin_user = UserOut(
        id="admin-uuid", email="admin@example.com", full_name="Admin", is_admin=True
    )

    sb_mock = _build_chained_mock(
        {
            "id": "p1",
            "name": "Acme",
            "slug": "acme",
            "user_id": admin_user.id,
            "is_active": True,
            "github_repo": "https://github.com/x/acme",
            "preview_url": "https://acme-dev.vercel.app",
        }
    )
    monkeypatch.setattr(deps, "get_supabase_admin", lambda: sb_mock)

    project = deps.require_project_access("acme", admin_user)

    # The SELECT must explicitly include these fields, otherwise Supabase
    # would not return them in production.
    sb_mock.select.assert_called_once()
    select_arg = sb_mock.select.call_args.args[0]
    assert "github_repo" in select_arg, f"SELECT missing github_repo: {select_arg!r}"
    assert "preview_url" in select_arg, f"SELECT missing preview_url: {select_arg!r}"

    # And the returned dict must carry them through (the slack_notify builders
    # call project.get("github_repo") / project.get("preview_url") directly).
    assert project["github_repo"] == "https://github.com/x/acme"
    assert project["preview_url"] == "https://acme-dev.vercel.app"


def test_require_project_access_selects_s1_5_fields(mock_supabase, admin_user):
    """Regression: deps.require_project_access must SELECT production_branch and
    production_url so the slack_handler approval flow has the fields it needs."""
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
