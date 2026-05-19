"""Slack notifications for project issues (outbound only).

Posts to `chat.postMessage` when an issue is created or resolved.
Disabled silently when env is unset; failures are logged but never
re-raised — Slack outages must not break issue create/update.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT_S = 5.0

_PRIORITY_EMOJI = {"High": "🔴", "Medium": "🟡", "Low": "🟢"}


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def _dashboard_url() -> str:
    return os.getenv("CMS_DASHBOARD_URL", "https://roman-technologies.dev").rstrip("/")


def _truncate(text: str, limit: int = 500) -> str:
    text = text or ""
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _post(blocks: list[dict], text_fallback: str, thread_ts: str | None = None) -> str | None:
    """POST one message to Slack. Returns the message ts on success, None on
    disabled mode or any failure. Swallow all errors."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping")
        return None
    try:
        body: dict[str, Any] = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text_fallback,
            "blocks": blocks,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=_TIMEOUT_S,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("slack_notify api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("slack_notify post failed")
        return None


def _build_created_blocks(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> list[dict]:
    project_name = project.get("name") or project.get("slug", "unknown")
    slug = project.get("slug", "unknown")
    branch = project.get("repo_branch", "dev")
    repo = project.get("github_repo") or "(repo not set)"
    priority = issue.get("priority", "Medium")
    emoji = _PRIORITY_EMOJI.get(priority, "⚪")
    desc = _truncate(issue.get("description", ""))
    dashboard = f"{_dashboard_url()}/dashboard/projects/{slug}/issues/{issue['id']}"

    return [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": f"🆕 New Issue — {project_name}", "emoji": True},
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{issue['title']}"},
                {"type": "mrkdwn", "text": f"*Priority:*\n{emoji} {priority}"},
                {"type": "mrkdwn", "text": f"*Submitted by:*\n{user_email or 'unknown'}"},
                {"type": "mrkdwn", "text": f"*Project:*\n{slug} (branch: {branch})"},
                {"type": "mrkdwn", "text": f"*Repo:*\n{repo}"},
            ],
        },
        {
            "type": "section",
            "text": {
                "type": "mrkdwn",
                "text": f"*Description:*\n>{desc.replace(chr(10), chr(10) + '>')}",
            },
        },
        {
            "type": "actions",
            "elements": [
                {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Open in CMS"},
                    "url": dashboard,
                }
            ],
        },
    ]


def _build_resolved_blocks(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> list[dict]:
    project_name = project.get("name") or project.get("slug", "unknown")
    slug = project.get("slug", "unknown")
    preview = project.get("preview_url")
    dashboard = f"{_dashboard_url()}/dashboard/projects/{slug}/issues/{issue['id']}"

    preview_line = preview if preview else "_(preview not configured)_"

    blocks: list[dict] = [
        {
            "type": "header",
            "text": {
                "type": "plain_text",
                "text": f"✅ Issue Resolved — {project_name}",
                "emoji": True,
            },
        },
        {
            "type": "section",
            "fields": [
                {"type": "mrkdwn", "text": f"*Title:*\n{issue['title']}"},
                {"type": "mrkdwn", "text": f"*Resolved by:*\n{resolver_email or 'unknown'}"},
                {"type": "mrkdwn", "text": f"*Preview:*\n{preview_line}"},
            ],
        },
    ]

    action_elements: list[dict] = []
    if preview:
        action_elements.append(
            {
                "type": "button",
                "text": {"type": "plain_text", "text": "Open Preview"},
                "url": preview,
            }
        )
    action_elements.append(
        {
            "type": "button",
            "text": {"type": "plain_text", "text": "Open in CMS"},
            "url": dashboard,
        }
    )
    blocks.append({"type": "actions", "elements": action_elements})
    return blocks


def notify_issue_created(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> str | None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping created")
        return None
    try:
        blocks = _build_created_blocks(issue, project, user_email)
        fallback = f"New issue [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        return _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (created) failed during build/post")
        return None


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> str | None:
    """Returns the Slack message ts on success, None otherwise."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping resolved")
        return None
    try:
        blocks = _build_resolved_blocks(issue, project, resolver_email)
        fallback = f"Resolved [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        return _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (resolved) failed during build/post")
        return None


_AGENT_EVENT_EMOJI = {
    "rejected": "🤔",
    "no_diff": "⚠️",
    "agent_crashed": "🔧",
    "backend_error": "🛑",
}

_AGENT_EVENT_HEADER = {
    "rejected": "Agent reviewed, no change",
    "no_diff": "Agent produced no file changes",
    "agent_crashed": "Agent CLI crashed",
    "backend_error": "Backend / push error",
}


def notify_agent_event(
    *,
    thread_ts: str | None,
    kind: str,
    reason: str,
    project: dict[str, Any],
    issue: dict[str, Any],
) -> str | None:
    """Post an agent-event Slack message.

    If thread_ts is provided, posts as a thread reply. If thread_ts is None
    (slack_created_ts was never persisted, e.g. notify_issue_created failed at
    create time), degrades to a top-level message that includes project + title
    for context.

    Returns the resulting Slack ts on success, None on disabled mode or any
    failure. Swallow all errors — slack outages must not break the agent.
    """
    if not _enabled():
        logger.info("slack_notify disabled — skipping agent_event")
        return None

    emoji = _AGENT_EVENT_EMOJI.get(kind, "❔")
    header = _AGENT_EVENT_HEADER.get(kind, "Agent event")
    project_name = project.get("name") or project.get("slug", "unknown")
    title = issue.get("title", "(no title)")
    reason_trimmed = _truncate(reason, 500)

    if thread_ts:
        text = f"{emoji} {header} — {reason_trimmed}"
    else:
        text = (
            f"{emoji} {header} — {project_name}\n"
            f"*Title:* {title}\n"
            f"*Reason:* {reason_trimmed}\n"
            f"_(threaded reply not possible — original 'New Issue' Slack ts unknown)_"
        )

    try:
        body: dict[str, Any] = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=_TIMEOUT_S,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("notify_agent_event api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("notify_agent_event post failed")
        return None


def post_thread_reply(*, thread_ts: str, text: str) -> str | None:
    """Reply in the thread of a previously-posted message.

    text is rendered as Slack mrkdwn. No blocks (simple reply).
    Returns the reply's ts on success, None otherwise.
    """
    if not _enabled():
        logger.info("slack_notify disabled — skipping thread reply")
        return None
    try:
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "thread_ts": thread_ts,
                "text": text,
            },
            timeout=_TIMEOUT_S,
        )
        data = resp.json()
        if not data.get("ok"):
            logger.warning("post_thread_reply api error: %s", data.get("error"))
            return None
        return data.get("ts")
    except Exception:
        logger.exception("post_thread_reply failed")
        return None
