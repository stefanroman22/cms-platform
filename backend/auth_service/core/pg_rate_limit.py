"""Postgres-backed shared rate limiter + login lockout (SEC-010/011/012/020).

The in-memory slowapi limiter resets per Vercel serverless invocation and is not
shared across warm instances, so its limits were effectively N×limit. These helpers
use a shared fixed-window counter in Postgres (the rate_limit_* RPCs) so a limit
holds across instances. All calls go through the service-role admin client.

Fail-open by design: a transient DB error must never lock every user out, so on
error `allow`/`enforce` permit the request and `over_limit` reports "not over".
"""

from __future__ import annotations

import logging

from fastapi import HTTPException, status

from ..services.supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


def allow(bucket: str, limit: int, window_seconds: int) -> bool:
    """Record a hit and return True if still within the limit (fail-open)."""
    try:
        res = (
            get_supabase_admin()
            .rpc(
                "rate_limit_hit",
                {"p_bucket": bucket, "p_limit": limit, "p_window_seconds": window_seconds},
            )
            .execute()
        )
        return bool(res.data)
    except Exception:
        logger.exception("rate_limit_hit failed; failing open (bucket=%s)", bucket)
        return True


def over_limit(bucket: str, limit: int, window_seconds: int) -> bool:
    """Return True if the bucket is already at/over the limit, WITHOUT counting a
    hit (fail-open → False)."""
    try:
        res = (
            get_supabase_admin()
            .rpc(
                "rate_limit_over",
                {"p_bucket": bucket, "p_limit": limit, "p_window_seconds": window_seconds},
            )
            .execute()
        )
        return bool(res.data)
    except Exception:
        logger.exception("rate_limit_over failed; failing open (bucket=%s)", bucket)
        return False


def reset(bucket: str) -> None:
    """Clear a bucket (e.g. on a successful login)."""
    try:
        get_supabase_admin().rpc("rate_limit_reset", {"p_bucket": bucket}).execute()
    except Exception:
        logger.exception("rate_limit_reset failed (bucket=%s)", bucket)


def enforce(
    bucket: str,
    limit: int,
    window_seconds: int,
    detail: str = "Too many requests. Please try again later.",
) -> None:
    """Count a hit and raise HTTP 429 if the bucket is over its limit."""
    if not allow(bucket, limit, window_seconds):
        raise HTTPException(status_code=status.HTTP_429_TOO_MANY_REQUESTS, detail=detail)
