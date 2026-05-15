"""Slack event idempotency.

Slack may redeliver the same event (network glitch, our timeout, etc).
We insert event_id with ON CONFLICT DO NOTHING semantics — but Supabase
client doesn't expose ON CONFLICT directly, so we do a SELECT-then-INSERT
pattern. Race conditions are acceptable: duplicate action is rare and
safe (merge is idempotent, email may double-send — acceptable for our
volume).
"""

from __future__ import annotations

import logging

from .supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def already_processed(event_id: str | None) -> bool:
    if not event_id:
        return False
    try:
        sb = get_supabase_admin()
        result = (
            sb.table("slack_processed_events")
            .select("event_id")
            .eq("event_id", event_id)
            .maybe_single()
            .execute()
        )
        return bool(result.data)
    except Exception:
        logger.exception("dedup lookup failed; treating as not-processed")
        return False


def mark_processed(event_id: str | None) -> None:
    if not event_id:
        return
    try:
        sb = get_supabase_admin()
        sb.table("slack_processed_events").insert({"event_id": event_id}).execute()
    except Exception:
        # DB error or unique-violation race. Either way, the caller already
        # decided to process this event; we don't want to abort that work.
        logger.exception("dedup insert failed (id=%s)", event_id)
