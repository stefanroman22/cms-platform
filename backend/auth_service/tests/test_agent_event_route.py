"""Tests for POST /admin/issues/{id}/agent-event — solver agent event notifications."""

from __future__ import annotations

from unittest.mock import MagicMock


def _issue_row(slack_created_ts: str | None = None) -> dict:
    return {
        "id": "issue-77",
        "project_id": "project-acme",
        "title": "Hero broken",
        "status": "pending",
        "slack_created_ts": slack_created_ts,
    }


def _project_row() -> dict:
    return {
        "id": "project-acme",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "production_branch": "main",
        "preview_url": "https://acme-cms-preview.vercel.app",
        "production_url": "https://acme.example.com",
        "user_id": "u1",
    }


def test_agent_event_threads_when_slack_created_ts_present(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)

    # Two select calls: issue lookup, project lookup.
    mock_supabase.execute.side_effect = [
        MagicMock(data=_issue_row(slack_created_ts="1715865123.456789")),  # issue lookup
        MagicMock(data=_project_row()),  # project lookup
    ]

    posted = {}
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_agent_event",
        lambda **kw: posted.update(kw) or "1715865500.000111",
    )

    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "Cannot reproduce"},
    )
    assert resp.status_code == 200, resp.text

    assert posted["thread_ts"] == "1715865123.456789"
    assert posted["kind"] == "rejected"
    assert posted["reason"] == "Cannot reproduce"


def test_agent_event_degrades_to_top_level_when_slack_created_ts_missing(
    mock_supabase, client, auth_as, admin_user, monkeypatch
):
    auth_as(admin_user)
    mock_supabase.execute.side_effect = [
        MagicMock(data=_issue_row(slack_created_ts=None)),
        MagicMock(data=_project_row()),
    ]

    posted = {}
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_agent_event",
        lambda **kw: posted.update(kw) or "ts-top-level",
    )

    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "no_diff", "reason": "no file changes"},
    )
    assert resp.status_code == 200, resp.text
    assert posted["thread_ts"] is None  # degraded path
    assert posted["kind"] == "no_diff"


def test_agent_event_404_when_issue_not_found(mock_supabase, client, auth_as, admin_user):
    auth_as(admin_user)
    mock_supabase.execute.return_value = MagicMock(data=None)
    resp = client.post(
        "/admin/issues/does-not-exist/agent-event",
        json={"kind": "rejected", "reason": "x"},
    )
    assert resp.status_code == 404


def test_agent_event_422_on_invalid_kind(client, auth_as, admin_user):
    auth_as(admin_user)
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "unknown_kind", "reason": "x"},
    )
    assert resp.status_code == 422


def test_agent_event_422_when_reason_too_long(client, auth_as, admin_user):
    auth_as(admin_user)
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "x" * 501},
    )
    assert resp.status_code == 422


def test_agent_event_requires_admin_auth(client):
    """No bearer/session → 401 or 403."""
    resp = client.post(
        "/admin/issues/issue-77/agent-event",
        json={"kind": "rejected", "reason": "x"},
    )
    assert resp.status_code in (401, 403)
