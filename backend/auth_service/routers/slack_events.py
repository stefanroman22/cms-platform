"""Slack Events API endpoint.

Receives reaction_added + message events from Slack and dispatches to
slack_handler. All requests pass HMAC verification (except the one-time
url_verification challenge sent during Slack app setup).
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Request, Response, status

from ..core.config import settings
from ..services import slack_events_dedup, slack_handler, slack_signature

router = APIRouter(tags=["slack"])
logger = logging.getLogger(__name__)


@router.post("/slack/events")
async def slack_events(request: Request) -> Response:
    body = await request.body()
    try:
        payload = await request.json()
    except Exception:
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    # URL verification challenge — one-shot during Slack app setup.
    # Slack docs say no signature is required on this single event.
    if payload.get("type") == "url_verification":
        return Response(content=payload.get("challenge", ""), media_type="text/plain")

    ts = request.headers.get("x-slack-request-timestamp", "")
    sig = request.headers.get("x-slack-signature", "")
    if not slack_signature.verify(ts, body, sig, settings.SLACK_SIGNING_SECRET):
        return Response(status_code=status.HTTP_401_UNAUTHORIZED)

    event_id = payload.get("event_id")
    if event_id and slack_events_dedup.already_processed(event_id):
        return Response(status_code=status.HTTP_200_OK)
    if event_id:
        slack_events_dedup.mark_processed(event_id)

    event = payload.get("event") or {}
    event_type = event.get("type")

    try:
        if event_type == "reaction_added":
            slack_handler.handle_reaction_added(event)
        elif event_type == "message":
            slack_handler.handle_message(event)
        # unknown types silently ignored
    except Exception:
        logger.exception("slack event handler raised; returning 200 anyway")

    return Response(status_code=status.HTTP_200_OK)
