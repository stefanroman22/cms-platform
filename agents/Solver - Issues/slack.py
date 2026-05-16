"""Slack notifications from the Solver Agent.

For routine outcomes (success, retry), the backend Slack machinery
(invoked via the admin endpoint) handles posting. For agent-internal
events that the backend doesn't know about — specifically the 'agent
blocked after N retries' notification — we POST directly to the
chat.postMessage API using the SLACK_BOT_TOKEN.

Disabled silently when SLACK_BOT_TOKEN or SLACK_ISSUES_CHANNEL_ID is unset.
"""

from __future__ import annotations

import logging
import os

import requests

logger = logging.getLogger(__name__)

_SLACK_API = "https://slack.com/api/chat.postMessage"
_TIMEOUT = 10


def _enabled() -> bool:
    return bool(os.getenv("SLACK_BOT_TOKEN") and os.getenv("SLACK_ISSUES_CHANNEL_ID"))


def post_blocked_notification(
    *,
    issue_id: str,
    title: str,
    project_name: str,
    retry_count: int,
    last_error: str,
) -> None:
    if not _enabled():
        logger.info("slack disabled — skipping blocked notification")
        return
    text = (
        f"🛑 *Agent gave up — {project_name}*\n"
        f"*Title:* {title}\n"
        f"*Tried:* {retry_count} times\n"
        f"*Last error:* {last_error[:300]}\n\n"
        f"This issue needs manual attention. Use the dashboard to reset agent_retry_count when ready."
    )
    try:
        response = requests.post(
            _SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json={
                "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
                "text": text,
            },
            timeout=_TIMEOUT,
        )
        body = response.json()
        if not body.get("ok"):
            logger.warning("slack post_blocked failed: %s", body.get("error"))
    except Exception:
        logger.exception("slack post_blocked exception")
