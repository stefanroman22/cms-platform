"""Slack notifications for project issues (outbound only).

Posts to `chat.postMessage` when an issue is created or resolved.
Disabled silently when env is unset; failures are logged but never
re-raised — Slack outages must not break issue create/update.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import httpx  # noqa: F401  # used by `_post` in later tasks; tests patch.object on this attr

logger = logging.getLogger(__name__)

SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT_S = 5.0


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def notify_issue_created(
    issue: dict[str, Any], project: dict[str, Any], user_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled (no token/channel) — skipping created")
        return
    # Real implementation arrives in later tasks.
    return


def notify_issue_resolved(
    issue: dict[str, Any], project: dict[str, Any], resolver_email: str | None
) -> None:
    if not _enabled():
        logger.info("slack_notify disabled (no token/channel) — skipping resolved")
        return
    return
