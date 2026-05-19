"""Glue layer — params + sinks in, counters out. Keeps google_maps.py
free of sink concerns and sinks free of scraping concerns."""

from __future__ import annotations

from dataclasses import dataclass

from loguru import logger

from .google_maps import scrape as _scrape
from .models import ScrapeParams
from .sinks.base import Sink


@dataclass
class Counters:
    found: int = 0
    inserted: int = 0
    skipped: int = 0


async def run_pipeline(
    params: ScrapeParams,
    sinks: list[Sink],
    scrape_job_id: str | None = None,
) -> Counters:
    counters = Counters()
    for s in sinks:
        await s.open()
    try:
        async for lead in _scrape(params, scrape_job_id=scrape_job_id):
            counters.found += 1
            any_inserted = False
            for s in sinks:
                ok = await s.write(lead)
                if ok:
                    any_inserted = True
                else:
                    counters.skipped += 1
            if any_inserted:
                counters.inserted += 1
        return counters
    finally:
        for s in sinks:
            try:
                await s.close()
            except Exception as exc:  # noqa: BLE001 — close failures don't mask main result
                logger.warning("sink close failed: {}", exc)
