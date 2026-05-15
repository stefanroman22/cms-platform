"""Integration tests for routers/issues.py — Slack notification wiring."""

from __future__ import annotations

from unittest.mock import MagicMock


def test_create_issue_fires_slack_created(mock_supabase, client, auth_as, client_user, monkeypatch):
    auth_as(client_user)

    # Stub Supabase insert to return one row.
    inserted_row = {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "created_at": "2026-05-15T10:00:00Z",
        "created_by": client_user.id,
    }
    mock_supabase.execute.return_value = MagicMock(data=[inserted_row])

    calls: list[dict] = []
    monkeypatch.setattr(
        "auth_service.routers.issues.slack_notify.notify_issue_created",
        lambda **kw: calls.append(kw),
    )

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "Hero broken", "description": "stretches", "priority": "High"},
    )
    assert resp.status_code == 201, resp.text

    assert len(calls) == 1
    call = calls[0]
    assert call["user_email"] == client_user.email
    assert call["issue"]["id"] == "issue-1"
    assert call["issue"]["title"] == "Hero broken"
    assert call["project"]["slug"] == "acme"
    assert call["project"]["repo_branch"] == "dev"


def test_create_issue_slack_failure_does_not_break_201(
    mock_supabase, client, auth_as, client_user, monkeypatch
):
    """If slack_notify raises, the API still returns 201."""
    auth_as(client_user)
    mock_supabase.execute.return_value = MagicMock(
        data=[
            {
                "id": "issue-2",
                "project_id": "project-acme",
                "title": "x",
                "description": "y",
                "priority": "Low",
                "created_at": "2026-05-15T10:00:00Z",
                "created_by": client_user.id,
            }
        ]
    )

    def boom(**kw):
        raise RuntimeError("slack down")

    monkeypatch.setattr("auth_service.routers.issues.slack_notify.notify_issue_created", boom)

    resp = client.post(
        "/projects/acme/issues",
        json={"title": "x", "description": "y", "priority": "Low"},
    )
    # The service itself swallows; if a router-level guard is missing, this test
    # forces it to be added.
    assert resp.status_code == 201, resp.text
