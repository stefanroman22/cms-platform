"""Supabase upsert sink. external_id is the conflict target."""

from __future__ import annotations

from loguru import logger
from supabase import Client, create_client

from ..config import settings
from ..models import Lead
from .base import Sink


class SupabaseSink(Sink):
    def __init__(self) -> None:
        self._sb: Client | None = None

    async def open(self) -> None:
        if not settings.SUPABASE_URL or not settings.SUPABASE_SERVICE_KEY:
            raise RuntimeError("SUPABASE_URL + SUPABASE_SERVICE_KEY required for SupabaseSink")
        self._sb = create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_KEY)

    async def write(self, lead: Lead) -> bool:
        if self._sb is None:
            raise RuntimeError("SupabaseSink.write called before open()")
        row = lead.model_dump(mode="json", exclude_none=False)
        try:
            self._sb.table("leads").upsert(row, on_conflict="external_id").execute()
            return True
        except Exception as exc:  # noqa: BLE001 — never break the scrape on a single bad row
            logger.warning("supabase upsert failed for {}: {}", lead.external_id, exc)
            return False

    async def close(self) -> None:
        return None
