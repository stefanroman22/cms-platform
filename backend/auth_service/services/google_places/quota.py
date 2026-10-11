"""Calendar-month Google import cap (ADR-0012). Fail-CLOSED: if the counter can't be
read or written, the import is refused rather than risking unbounded spend."""

from __future__ import annotations

import logging

from ...core.config import settings
from ..supabase_client import get_supabase_admin

logger = logging.getLogger(__name__)


class MonthlyCapReached(Exception):
    pass


class QuotaUnavailable(Exception):
    pass


def _rpc(name: str) -> bool:
    try:
        res = (
            get_supabase_admin()
            .rpc(name, {"p_limit": settings.GOOGLE_PLACES_MONTHLY_CAP})
            .execute()
        )
    except Exception as e:  # noqa: BLE001 — any counter failure blocks the paid call
        logger.exception("%s failed; refusing Google import", name)
        raise QuotaUnavailable() from e
    return bool(res.data) if res is not None else False


def ensure_not_over() -> None:
    """Raise MonthlyCapReached when this month is already at the cap (no increment)."""
    if _rpc("google_import_over"):
        raise MonthlyCapReached()


def consume() -> None:
    """Count one paid Google call against this month, or raise MonthlyCapReached."""
    if not _rpc("google_import_hit"):
        raise MonthlyCapReached()
