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


def _post(blocks: list[dict], text_fallback: str) -> None:
    """POST one message to Slack. Swallow all errors."""
    if not _enabled():
        logger.info("slack_notify disabled — skipping")
        return
    try:
        resp = httpx.post(
            SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "text": text_fallback,
                "blocks": blocks,
            },
            timeout=_TIMEOUT_S,
        )
        body = resp.json()
        if not body.get("ok"):
            logger.warning("slack_notify api error: %s", body.get("error"))
    except Exception:
        logger.exception("slack_notify post failed")


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
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping created")
        return
    try:
        blocks = _build_created_blocks(issue, project, user_email)
        fallback = f"New issue [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (created) failed during build/post")


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled — skipping resolved")
        return
    try:
        blocks = _build_resolved_blocks(issue, project, resolver_email)
        fallback = f"Resolved [{project.get('slug', '?')}]: {issue.get('title', '?')}"
        _post(blocks, fallback)
    except Exception:  # noqa: BLE001 — public API must never re-raise
        logger.exception("slack_notify (resolved) failed during build/post")
