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


def test_created_does_not_raise_on_malformed_issue(monkeypatch, caplog):
    """A malformed issue dict (missing keys) must NOT raise — service docstring promise."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    with patch.object(slack_notify.httpx, "post") as mock_post:
        with caplog.at_level("ERROR"):
            # Empty issue dict — no id, no title, no description, no priority.
            slack_notify.notify_issue_created(
                issue={},
                project=_sample_project(),
                user_email="client@acme.com",
            )

    # The function returned cleanly (no exception bubbled out).
    # It may or may not have called httpx.post depending on where the failure happened —
    # the important contract is "no exception escapes".
    assert (
        any("slack_notify (created) failed" in rec.message for rec in caplog.records)
        or mock_post.called
    )  # one of the two: either we logged the failure OR we posted with sentinel values


def test_resolved_posts_to_slack_with_expected_payload(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")
    monkeypatch.setenv("CMS_DASHBOARD_URL", "https://cms.example.com")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    body = captured["json"]
    assert "Resolved" in body["text"]
    assert "acme-site" in body["text"]

    blocks_text = str(body["blocks"])
    assert "Issue Resolved" in blocks_text
    assert "Hero image broken on mobile" in blocks_text
    assert "stefan@example.com" in blocks_text
    assert "https://acme-site-dev.vercel.app" in blocks_text  # preview URL
    assert "https://cms.example.com" in blocks_text  # dashboard link


def test_resolved_no_preview_url_omits_preview_section(monkeypatch):
    """Project without preview_url should still produce a valid message."""
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    project = _sample_project()
    project["preview_url"] = None

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=project,
            resolver_email="stefan@example.com",
        )

    blocks_text = str(captured["json"]["blocks"])
    assert "preview not configured" in blocks_text.lower()


def test_swallows_timeout(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    def fake_post(*args, **kwargs):
        raise slack_notify.httpx.TimeoutException("slow")

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        # Must not raise.
        slack_notify.notify_issue_created(
            issue=_sample_issue(),
            project=_sample_project(),
            user_email="client@acme.com",
        )


def test_swallows_api_error_ok_false(monkeypatch, caplog):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _ErrResp:
        def json(self):
            return {"ok": False, "error": "not_in_channel"}

    def fake_post(*args, **kwargs):
        return _ErrResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        with caplog.at_level("WARNING"):
            slack_notify.notify_issue_resolved(
                issue=_sample_issue(),
                project=_sample_project(),
                resolver_email="stefan@example.com",
            )

    assert any("not_in_channel" in rec.message for rec in caplog.records)


def test_resolved_returns_slack_ts(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _OkResp:
        def json(self):
            return {"ok": True, "ts": "1715789123.001234"}

    with patch.object(slack_notify.httpx, "post", return_value=_OkResp()):
        ts = slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    assert ts == "1715789123.001234"


def test_resolved_returns_none_when_disabled(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)
    ts = slack_notify.notify_issue_resolved(
        issue=_sample_issue(),
        project=_sample_project(),
        resolver_email="stefan@example.com",
    )
    assert ts is None


def test_resolved_returns_none_on_api_error(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    class _ErrResp:
        def json(self):
            return {"ok": False, "error": "not_in_channel"}

    with patch.object(slack_notify.httpx, "post", return_value=_ErrResp()):
        ts = slack_notify.notify_issue_resolved(
            issue=_sample_issue(),
            project=_sample_project(),
            resolver_email="stefan@example.com",
        )

    assert ts is None


def test_post_thread_reply_posts_with_thread_ts(monkeypatch):
    monkeypatch.setenv("SLACK_BOT_TOKEN", "xoxb-test")
    monkeypatch.setenv("SLACK_ISSUES_CHANNEL_ID", "C123")

    captured = {}

    class _OkResp:
        def json(self):
            return {"ok": True, "ts": "1715789200.000001"}

    def fake_post(url, headers, json, timeout):
        captured["json"] = json
        return _OkResp()

    with patch.object(slack_notify.httpx, "post", side_effect=fake_post):
        slack_notify.post_thread_reply(
            thread_ts="1715789123.001234", text="🚀 Promoted to production."
        )

    body = captured["json"]
    assert body["channel"] == "C123"
    assert body["thread_ts"] == "1715789123.001234"
    assert body["text"] == "🚀 Promoted to production."


def test_post_thread_reply_disabled_no_op(monkeypatch):
    monkeypatch.delenv("SLACK_BOT_TOKEN", raising=False)
    monkeypatch.delenv("SLACK_ISSUES_CHANNEL_ID", raising=False)
    with patch.object(slack_notify.httpx, "post") as mock_post:
        slack_notify.post_thread_reply(thread_ts="x", text="y")
        mock_post.assert_not_called()
