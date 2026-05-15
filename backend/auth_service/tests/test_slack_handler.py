"""Slack inbound event handler unit tests — reaction approval flow."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ..services import slack_handler


def _stefan() -> str:
    return "U_STEFAN"


def _bot() -> str:
    return "U_BOT"


def _channel() -> str:
    return "C_ISSUES"


def _issue_done() -> dict:
    return {
        "id": "issue-1",
        "project_id": "project-acme",
        "title": "Hero broken",
        "description": "stretches",
        "status": "done",
        "created_by": "client-uid",
        "slack_resolved_ts": "1715789123.001234",
    }


def _project() -> dict:
    return {
        "id": "project-acme",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
        "production_branch": "master",
        "production_url": "https://acme.example.com",
    }


def _event_reaction(emoji: str = "white_check_mark", user: str | None = None) -> dict:
    return {
        "type": "reaction_added",
        "reaction": emoji,
        "user": user or _stefan(),
        "item": {"type": "message", "ts": "1715789123.001234", "channel": _channel()},
    }


@pytest.fixture
def slack_env(monkeypatch):
    monkeypatch.setattr(slack_handler.settings, "SLACK_ISSUES_CHANNEL_ID", _channel())
    monkeypatch.setattr(slack_handler.settings, "SLACK_APPROVER_USER_ID", _stefan())
    monkeypatch.setattr(slack_handler.settings, "SLACK_BOT_USER_ID", _bot())


def test_reaction_wrong_emoji_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction(emoji="thumbsup"))
        ack.assert_not_called()


def test_reaction_wrong_channel_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    event = _event_reaction()
    event["item"]["channel"] = "C_OTHER"
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(event)
        ack.assert_not_called()


def test_reaction_unknown_message_noop(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: None)
    with patch.object(slack_handler, "_post_thread_reply") as ack:
        slack_handler.handle_reaction_added(_event_reaction())
        ack.assert_not_called()


def test_reaction_wrong_user_warns_no_merge(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    with (
        patch.object(slack_handler, "github_merge") as merge,
        patch.object(slack_handler, "_post_thread_reply") as ack,
    ):
        slack_handler.handle_reaction_added(_event_reaction(user="U_OTHER"))
        merge.fast_forward.assert_not_called()
        ack.assert_called_once()
        assert "Only Stefan" in ack.call_args.args[1]


def test_reaction_issue_not_done_warns(slack_env, monkeypatch):
    issue = _issue_done()
    issue["status"] = "pending"
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: issue)
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    with (
        patch.object(slack_handler, "github_merge") as merge,
        patch.object(slack_handler, "_post_thread_reply") as ack,
    ):
        slack_handler.handle_reaction_added(_event_reaction())
        merge.fast_forward.assert_not_called()
        ack.assert_called_once()
        assert "pending" in ack.call_args.args[1]


def test_reaction_happy_path(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    monkeypatch.setattr(slack_handler, "_email_for_user", lambda uid: "client@acme.com")
    monkeypatch.setattr(slack_handler, "_clear_revision_feedback", lambda iid: None)

    with (
        patch.object(
            slack_handler.github_merge,
            "fast_forward",
            return_value={"object": {"sha": "abc123def4567"}},
        ) as merge,
        patch.object(
            slack_handler.issue_resolved_email, "send", return_value={"id": "email_1"}
        ) as email,
        patch.object(slack_handler, "_post_thread_reply") as ack,
    ):
        slack_handler.handle_reaction_added(_event_reaction())

    merge.assert_called_once()
    kwargs = merge.call_args.kwargs
    assert kwargs["repo"] == "stefan/acme"
    assert kwargs["base_branch"] == "master"
    assert kwargs["head_branch"] == "cms-preview"

    email.assert_called_once()
    assert email.call_args.kwargs["to_email"] == "client@acme.com"

    ack.assert_called_once()
    text = ack.call_args.args[1]
    assert "🚀" in text
    assert "abc123d" in text  # short SHA prefix


def test_reaction_merge_diverged_posts_failure_no_email(slack_env, monkeypatch):
    from ..services.github_merge import GitHubError

    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())

    with (
        patch.object(
            slack_handler.github_merge, "fast_forward", side_effect=GitHubError("diverged")
        ) as merge,
        patch.object(slack_handler.issue_resolved_email, "send") as email,
        patch.object(slack_handler, "_post_thread_reply") as ack,
    ):
        slack_handler.handle_reaction_added(_event_reaction())

    merge.assert_called_once()
    email.assert_not_called()
    ack.assert_called_once()
    assert "❌" in ack.call_args.args[1]
    assert "diverged" in ack.call_args.args[1]


def test_reaction_email_failure_partial_success(slack_env, monkeypatch):
    monkeypatch.setattr(slack_handler, "_find_issue_by_slack_ts", lambda ts: _issue_done())
    monkeypatch.setattr(slack_handler, "_get_project_full", lambda pid: _project())
    monkeypatch.setattr(slack_handler, "_email_for_user", lambda uid: "client@acme.com")

    with (
        patch.object(
            slack_handler.github_merge, "fast_forward", return_value={"object": {"sha": "abc"}}
        ),
        patch.object(
            slack_handler.issue_resolved_email, "send", side_effect=RuntimeError("resend down")
        ),
        patch.object(slack_handler, "_post_thread_reply") as ack,
    ):
        slack_handler.handle_reaction_added(_event_reaction())

    ack.assert_called_once()
    text = ack.call_args.args[1]
    assert "⚠️" in text
    assert "email" in text.lower()
