"""Slack Events API handlers — reaction (approve) + message (revision) flows.

This module is invoked by the /slack/events router. The reaction handler
fires production-promote + client email when Stefan ✅ a resolved-issue
message. The message handler (Task 10) handles thread-reply revision
feedback.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime

from ..core.config import settings
from . import github_merge, issue_resolved_email, slack_notify
from .supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def handle_reaction_added(event: dict) -> None:
    """Stefan ✅ on a tracked resolved-issue message → publish + email."""
    if event.get("reaction") != "white_check_mark":
        return

    item = event.get("item", {})
    if item.get("type") != "message":
        return

    msg_ts = item.get("ts")
    channel = item.get("channel")
    if not msg_ts or channel != settings.SLACK_ISSUES_CHANNEL_ID:
        return

    issue = _find_issue_by_slack_ts(msg_ts)
    if not issue:
        logger.info("reaction on untracked message ts=%s — ignoring", msg_ts)
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        _post_thread_reply(msg_ts, "⚠️ Only Stefan can approve. Reaction ignored.")
        return

    if issue["status"] != "done":
        _post_thread_reply(msg_ts, f"⚠️ Issue is `{issue['status']}` — cannot approve.")
        return

    project = _get_project_full(issue["project_id"])

    try:
        merge_result = github_merge.fast_forward(
            repo=project["github_repo"],
            base_branch=project["production_branch"],
            head_branch=project["repo_branch"],
        )
    except github_merge.GitHubError as e:
        _post_thread_reply(msg_ts, f"❌ Production merge failed: {e}")
        return

    try:
        issue_resolved_email.send(
            to_email=_email_for_user(issue["created_by"]),
            issue=issue,
            project=project,
        )
    except Exception:
        logger.exception("client email failed but production merge succeeded")
        _post_thread_reply(
            msg_ts,
            f"⚠️ Merged to `{project['production_branch']}` but email failed. "
            f"Notify client manually. Deployment: {project.get('production_url') or '(unknown)'}",
        )
        return

    _clear_revision_feedback(issue["id"])

    sha = merge_result.get("object", {}).get("sha", "?")[:7]
    _post_thread_reply(
        msg_ts,
        f"🚀 *Promoted to production.*\n"
        f"• Merged `{project['repo_branch']}` → `{project['production_branch']}` (SHA `{sha}`)\n"
        f"• Email sent to client\n"
        f"• Production: {project.get('production_url') or '(deploy in progress)'}",
    )


def handle_message(event: dict) -> None:
    """Stefan replies in the resolved-issue thread → revert + store feedback."""
    if event.get("subtype") == "bot_message":
        return
    if event.get("bot_id") or event.get("user") == settings.SLACK_BOT_USER_ID:
        return

    channel = event.get("channel")
    thread_ts = event.get("thread_ts")
    text = (event.get("text") or "").strip()

    if channel != settings.SLACK_ISSUES_CHANNEL_ID or not thread_ts:
        return

    issue = _find_issue_by_slack_ts(thread_ts)
    if not issue:
        return

    if event.get("user") != settings.SLACK_APPROVER_USER_ID:
        return

    if issue["status"] != "done":
        _post_thread_reply(
            thread_ts,
            f"⚠️ Issue is `{issue['status']}` — cannot mark as needs revision.",
        )
        return

    if len(text) < 5:
        return

    sb = get_supabase_admin()
    sb.table("project_issues").update(
        {
            "status": "in_progress",
            "revision_feedback": text,
            "revision_feedback_at": datetime.now(UTC).isoformat(),
            "agent_status": "idle",  # S3: clear lock
            "agent_retry_count": 0,  # S3: fresh attempt budget
            "agent_last_error": None,  # S3: clear stale error
        }
    ).eq("id", issue["id"]).execute()

    excerpt = text[:120] + ("…" if len(text) > 120 else "")
    _post_thread_reply(
        thread_ts,
        f"📝 *Marked as needs revision.*\n> {excerpt}\n\n"
        f"Issue moved back to `in_progress`. Fix on `cms-preview` and "
        f"mark done again to re-trigger approval.",
    )


# ── private helpers ──────────────────────────────────────────────────────────


def _find_issue_by_slack_ts(ts: str) -> dict | None:
    sb = get_supabase_admin()
    result = (
        sb.table("project_issues")
        .select("id, project_id, title, description, status, created_by, slack_resolved_ts")
        .eq("slack_resolved_ts", ts)
        .maybe_single()
        .execute()
    )
    return result.data


def _get_project_full(project_id: str) -> dict:
    sb = get_supabase_admin()
    result = (
        sb.table("projects")
        .select(
            "id, name, slug, github_repo, repo_branch, production_branch, production_url, user_id"
        )
        .eq("id", project_id)
        .single()
        .execute()
    )
    return result.data or {}


def _email_for_user(user_id: str | None) -> str:
    if not user_id:
        return ""
    sb = get_supabase_admin()
    result = sb.table("users").select("email").eq("id", user_id).maybe_single().execute()
    return (result.data or {}).get("email", "") if result else ""


def _clear_revision_feedback(issue_id: str) -> None:
    sb = get_supabase_admin()
    sb.table("project_issues").update({"revision_feedback": None, "revision_feedback_at": None}).eq(
        "id", issue_id
    ).execute()


def _post_thread_reply(thread_ts: str, text: str) -> None:
    slack_notify.post_thread_reply(thread_ts=thread_ts, text=text)
