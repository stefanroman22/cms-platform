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
    "menu": lambda lead: lead.menu_url,
    "status website": lambda lead: "not_started",
    "status ai workflow": lambda lead: "not_started",
    "status lead": lambda lead: "not_sent",
    "type lead": lambda lead: lead.lead_type,
    "payment": lambda lead: "not_applicable",
}


class SheetsSink(Sink):
    def __init__(self) -> None:
        self._ws: gspread.Worksheet | None = None
        self._headers: list[str] = []

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

    async def write(self, lead: Lead) -> bool:
        assert self._ws is not None
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
            return True
        except Exception as exc:  # noqa: BLE001 — never break the scrape on a single bad row
            logger.warning("sheets append failed for {}: {}", lead.external_id, exc)
            return False

    async def close(self) -> None:
        return None
