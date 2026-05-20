"""Append rows into the existing 18-column Google Sheet, mapping fields
by header name. Header row in the sheet is the source of truth for
which columns receive data — fields the sheet doesn't have stay
Supabase-only."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

import gspread
from google.oauth2.service_account import Credentials
from loguru import logger

from ..config import settings
from ..models import Lead
from .base import Sink

_SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]


# Map: Sheet column header (case-insensitive) → callable(Lead) -> value.
# Add new fields here as the sheet grows; missing headers are skipped.
_FIELD_MAP: dict[str, Callable[[Lead], Any]] = {
    "name": lambda lead: lead.business_name,
    "city": lambda lead: lead.city,
    "adress": lambda lead: lead.address,  # sic — existing typo in sheet
    "address": lambda lead: lead.address,
    "contact email": lambda lead: lead.email,
    "contact phone": lambda lead: lead.phone,
    "category": lambda lead: lead.category,
    "description": lambda lead: lead.description,
    "reviews array": lambda lead: lead.reviews,
    "review average": lambda lead: lead.rating,
    "schedule": lambda lead: lead.opening_hours,
    "about": lambda lead: lead.about,
    "photos": lambda lead: ",".join(lead.photo_urls) if lead.photo_urls else None,
    "menu": lambda lead: None,
    "status website": lambda lead: None,
    "status ai workflow": lambda lead: None,
    "status lead": lambda lead: None,
    "type lead": lambda lead: lead.lead_type,
    "payment": lambda lead: None,
    # CMS-managed fields — humans fill these via the dashboard after a deal
    # closes. The scraper-side Lead model doesn't carry them; getattr returns
    # None so the sheet columns stay empty for scrape inserts. Add "Closed
    # Amount" + "Closed Date" header cells to the sheet manually.
    "closed amount": lambda lead: getattr(lead, "closed_amount", None),
    "closed date": lambda lead: getattr(lead, "closed_at", None),
    # Dedup key — sink reads this column at open() time to populate _seen
    # and skip append for rows already present. Add an "External ID" header
    # cell to the sheet to enable cross-run dedup.
    "external id": lambda lead: lead.external_id,
}

# Header label the sink uses to populate its _seen set. Case-insensitive
# match against the sheet's row-1 headers.
_EXTERNAL_ID_HEADER = "external id"


class SheetsSink(Sink):
    def __init__(self) -> None:
        self._ws: gspread.Worksheet | None = None
        self._headers: list[str] = []
        # external_ids already present on the sheet — populated at open(),
        # mutated by write(). Cross-run dedup hinges on the sheet having an
        # "External ID" column; without it, _seen stays empty and the sink
        # falls back to append-only behaviour.
        self._seen: set[str] = set()

    async def open(self) -> None:
        if not settings.GOOGLE_SHEETS_CREDENTIALS_JSON or not settings.GOOGLE_SHEET_ID:
            raise RuntimeError(
                "Sheets sink requires GOOGLE_SHEETS_CREDENTIALS_JSON + GOOGLE_SHEET_ID"
            )
        creds = Credentials.from_service_account_file(
            settings.GOOGLE_SHEETS_CREDENTIALS_JSON, scopes=_SCOPES
        )
        gc = gspread.authorize(creds)
        sh = gc.open_by_key(settings.GOOGLE_SHEET_ID)
        self._ws = sh.sheet1
        self._headers = [h.strip() for h in self._ws.row_values(1)]
        # Build the dedup set from the existing sheet contents if an
        # "External ID" column exists. One extra read at start; cheaper
        # than appending duplicates and cleaning up later.
        ext_id_col = next(
            (i + 1 for i, h in enumerate(self._headers) if h.lower() == _EXTERNAL_ID_HEADER),
            None,
        )
        if ext_id_col is None:
            logger.warning(
                "sheet has no 'External ID' column — running in append-only "
                "mode; duplicate rows possible. Add the header to enable dedup."
            )
            return
        # col_values returns header + data; skip row 1.
        existing = self._ws.col_values(ext_id_col)
        for val in existing[1:]:
            v = str(val).strip() if val is not None else ""
            if v:
                self._seen.add(v)
        logger.info("sheets sink dedup: {} existing external_ids loaded", len(self._seen))

    async def write(self, lead: Lead) -> bool:
        if self._ws is None:
            raise RuntimeError("SheetsSink.write called before open()")
        if lead.external_id in self._seen:
            logger.debug("sheets dedup skip: {}", lead.external_id)
            return False
        row: list[Any] = []
        for header in self._headers:
            key = header.lower()
            fn = _FIELD_MAP.get(key)
            if fn is None:
                row.append("")
                continue
            value = fn(lead)
            row.append("" if value is None else str(value))
        try:
            self._ws.append_row(row, value_input_option="RAW")
            self._seen.add(lead.external_id)
            return True
        except Exception as exc:  # noqa: BLE001 — never break the scrape on a single bad row
            logger.warning("sheets append failed for {}: {}", lead.external_id, exc)
            return False

    async def close(self) -> None:
        return None
