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


def _sample_issue() -> dict:
    return {
        "id": "i1",
        "title": "Hero image broken on mobile",
        "description": "Image stretches off-screen on iPhone Safari 17.",
        "priority": "High",
        "created_at": "2026-05-15T10:00:00Z",
    }


def _sample_project() -> dict:
    return {
        "id": "p1",
        "slug": "acme-site",
        "name": "Acme Site",
        "github_repo": "https://github.com/stefan/acme-site",
        "repo_branch": "dev",
        "preview_url": "https://acme-site-dev.vercel.app",
    }


def test_created_posts_to_slack_with_expected_payload(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")
    monkeypatch.setenv("CMS_DASHBOARD_URL", "https://cms.example.com")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["url"] = url
        captured["headers"] = headers
        captured["json"] = json
        captured["timeout"] = timeout
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_created(
            issue=_sample_issue(),
            project=_sample_project(),
            user_email="client@acme.com",
        )

    assert captured["url"] == slack_notify.SLACK_API
    assert captured["headers"]["Authorization"] == "Bearer xoxb-test"
    assert captured["timeout"] == 5.0

    body = captured["json"]
    assert body["channel"] == "C123"
    assert "New issue" in body["text"]
    assert "acme-site" in body["text"]
    assert "Hero image broken on mobile" in body["text"]

    # Block kit content: title, priority, submitter, project line, repo line, description, button
    blocks_text = str(body["blocks"])
    assert "Hero image broken on mobile" in blocks_text
    assert "High" in blocks_text
    assert "client@acme.com" in blocks_text
    assert "acme-site" in blocks_text
    assert "dev" in blocks_text
    assert "github.com/stefan/acme-site" in blocks_text
    assert "Image stretches" in blocks_text
    assert "https://cms.example.com" in blocks_text  # dashboard link
