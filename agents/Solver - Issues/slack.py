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


_EVENT_EMOJI = {
    "rejected": "🤔",
    "no_diff": "⚠️",
    "agent_crashed": "🔧",
    "backend_error": "🛑",
}

_EVENT_HEADER = {
    "rejected": "Agent reviewed, no change",
    "no_diff": "Agent produced no file changes",
    "agent_crashed": "Agent CLI crashed",
    "backend_error": "Backend / push error",
}


def post_thread_event_direct(
    *,
    thread_ts: str | None,
    kind: str,
    reason: str,
) -> None:
    """Direct chat.postMessage thread reply — fallback when backend is failing.

    Used by finalize.py when trigger_issue_resolved exhausts its retries; at
    that point we can't reach the backend's /admin/issues/{id}/agent-event
    route to post the event, so we go direct to Slack with the same emoji +
    header convention.

    Silently disabled when SLACK_BOT_TOKEN or SLACK_ISSUES_CHANNEL_ID is unset.
    Never raises.
    """
    if not _enabled():
        logger.info("slack disabled — skipping post_thread_event_direct")
        return

    emoji = _EVENT_EMOJI.get(kind, "❔")
    header = _EVENT_HEADER.get(kind, "Agent event")
    reason_trimmed = (reason or "")[:500]
    text = f"{emoji} {header} — {reason_trimmed}"

    try:
        body: dict = {
            "channel": os.environ["SLACK_ISSUES_CHANNEL_ID"],
            "text": text,
        }
        if thread_ts:
            body["thread_ts"] = thread_ts
        response = requests.post(
            _SLACK_API,
            headers={
                "Authorization": f"Bearer {os.environ['SLACK_BOT_TOKEN']}",
                "Content-Type": "application/json; charset=utf-8",
            },
            json=body,
            timeout=_TIMEOUT,
        )
        body = response.json()
        if not body.get("ok"):
            logger.warning("post_thread_event_direct failed: %s", body.get("error"))
    except Exception:
        logger.exception("post_thread_event_direct exception")
