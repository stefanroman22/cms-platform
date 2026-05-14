"""Unit tests for slack_notify service."""

from __future__ import annotations

from unittest.mock import patch

from ..services import slack_notify


def test_disabled_when_env_missing(monkeypatch):
    """No token + no channel → no HTTP call made."""
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)

    with patch.object(slack_notify, "httpx") as mock_httpx:
        slack_notify.notify_issue_created(
            issue={
                "id": "i1",
                "title": "Hero broken",
                "description": "stretches",
                "priority": "High",
                "created_at": "2026-05-15T10:00:00Z",
            },
            project={
                "id": "p1",
                "slug": "acme",
                "name": "Acme",
                "github_repo": "github.com/x/acme",
                "repo_branch": "dev",
            },
            user_email="client@acme.com",
        )
        mock_httpx.post.assert_not_called()
