"""Orchestrates one import: resolve -> details -> map -> enrich -> insert -> photos
(ADR-0012). Everything Google-sourced is listed in GOOGLE_FIELDS so a re-import can
fill gaps or overwrite without ever touching pipeline fields."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime

from ...core.config import settings
from . import client
from .mapper import MappedPlace, map_place
from .photos import delete_lead_photos, download_photos
from .quota import (  # noqa: F401 — MonthlyCapReached/QuotaUnavailable re-exported
    MonthlyCapReached,
    QuotaUnavailable,
    consume,
    ensure_not_over,
)
from .resolve import classify, resolve
from .website_enrich import enrich_from_website

logger = logging.getLogger(__name__)

GOOGLE_FIELDS = frozenset(
    {
        "business_name",
        "name_normalized",
        "category",
        "description",
        "about",
        "country",
        "region",
        "city",
        "address",
        "postal_code",
        "lat",
        "lng",
        "phone",
        "email",
        "website_url",
        "facebook_url",
        "instagram_url",
        "social_links",
        "web_presence",
        "rating",
        "review_count",
        "reviews",
        "opening_hours",
        "photo_urls",
        "business_status",
        "primary_type",
        "types",
        "price_level",
        "source_url",
        "google_place_id",
        "google_imported_at",
        "extra",
    }
)
ALWAYS_REFRESH = frozenset(
    {"rating", "review_count", "business_status", "google_imported_at", "google_place_id"}
)


class DuplicateLead(Exception):
    def __init__(self, lead_id: str):
        super().__init__(lead_id)
        self.lead_id = lead_id


class MissingPlaceId(ValueError):
    pass


@dataclass
class ImportOutcome:
    lead: dict | None
    candidates: list[dict] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _empty(v) -> bool:
    return v is None or v == "" or v == [] or v == {}


def build_row(
    mapped: MappedPlace, enrichment: dict | None, *, place_id: str, language: str, now_iso: str
) -> dict:
    row = dict(mapped.columns)
    social: dict[str, str] = {}
    if row.get("facebook_url"):
        social["facebook"] = row["facebook_url"]
    if row.get("instagram_url"):
        social["instagram"] = row["instagram_url"]
    row["email"] = None
    if enrichment and enrichment.get("fetched"):
        for platform, url in (enrichment.get("social_links") or {}).items():
            social.setdefault(platform, url)
        row["email"] = enrichment.get("email")
        if enrichment.get("description"):
            row["description"] = enrichment["description"]
    row.setdefault("description", None)
    row["social_links"] = social
    row["facebook_url"] = social.get("facebook")
    row["instagram_url"] = social.get("instagram")
    row["google_place_id"] = place_id
    row["google_imported_at"] = now_iso
    row["external_id"] = f"google:{place_id}"
    row["primary_source"] = "google_maps"
    row["_enriched"] = bool(enrichment and enrichment.get("fetched"))
    row["extra"] = {
        "attributes": mapped.attributes,
        "google": {
            **mapped.google,
            "place_id": place_id,
            "language": language,
            "imported_at": now_iso,
            "photos": [],
            "website": enrichment,
        },
    }
    return row


def merge_fill_empty(current: dict, incoming: dict) -> dict:
    """Patch = incoming values for Google fields that are empty on `current`, plus
    ALWAYS_REFRESH fields. `extra` keeps current keys and replaces only `google`."""
    patch: dict = {}
    for key, value in incoming.items():
        if key not in GOOGLE_FIELDS or key == "extra":
            continue
        current_value = current.get(key)
        if key == "web_presence" and current_value == "unknown":
            current_value = None  # 'unknown' is a placeholder, not data
        if key in ALWAYS_REFRESH or _empty(current_value):
            patch[key] = value
    cur_extra = dict(current.get("extra") or {})
    inc_extra = incoming.get("extra") or {}
    cur_extra["google"] = inc_extra.get("google", {})
    if _empty(cur_extra.get("attributes")):
        cur_extra["attributes"] = inc_extra.get("attributes", {})
    patch["extra"] = cur_extra
    return patch


def _fetch_and_map(place_id: str, language: str) -> tuple[dict, list[str]]:
    """Details + enrichment -> (row without photos, warnings). Counts the monthly hit."""
    consume()
    place = client.place_details(place_id, language=language)
    mapped = map_place(place, language=language)
    warnings: list[str] = []
    enrichment = None
    if mapped.website_uri and mapped.columns.get("web_presence") == "has_website":
        enrichment = enrich_from_website(mapped.website_uri)
        if enrichment.get("error"):
            warnings.append(f"website enrichment skipped: {enrichment['error']}")
    row = build_row(
        mapped,
        enrichment,
        place_id=place_id,
        language=language,
        now_iso=datetime.now(UTC).isoformat(),
    )
    row["_photos"] = mapped.photos
    return row, warnings


def _consume_if_text(raw_input: str) -> None:
    """Free text goes to paid Text Search, so it takes a monthly slot of its own; a text
    search that then also needs Place Details therefore uses two slots (accepted)."""
    if classify(raw_input)[0] == "text":
        consume()


def _attach_photos(sb, lead_id: str, row: dict, extra: dict) -> tuple[dict, list[str]]:
    urls, meta, warnings = download_photos(
        sb,
        lead_id,
        row["business_name"],
        row.pop("_photos", []),
        max_photos=settings.GOOGLE_PLACES_MAX_PHOTOS,
    )
    google = dict(extra.get("google") or {})
    google["photos"] = meta
    extra = {**extra, "google": google}
    return {"photo_urls": urls, "extra": extra}, warnings


def _find_duplicate(sb, place_id: str) -> str | None:
    res = sb.table("leads").select("id").eq("google_place_id", place_id).maybe_single().execute()
    return res.data.get("id") if res and res.data else None


def _find_by_external_id(sb, place_id: str) -> str | None:
    res = (
        sb.table("leads")
        .select("id")
        .eq("external_id", f"google:{place_id}")
        .maybe_single()
        .execute()
    )
    return res.data.get("id") if res and res.data else None


def _is_unique_violation(e: Exception) -> bool:
    return "23505" in str(e) or "duplicate" in str(e).lower()


def _with_warnings(extra: dict, warnings: list[str]) -> dict:
    """extra with the import warnings stored under google.import_warnings (if any)."""
    if not warnings:
        return extra
    return {**extra, "google": {**(extra.get("google") or {}), "import_warnings": list(warnings)}}


def import_place(sb, *, raw_input: str, lead_type: str, language: str) -> ImportOutcome:
    ensure_not_over()
    _consume_if_text(raw_input)
    resolution = resolve(raw_input, language=language)
    if resolution.place_id is None:
        return ImportOutcome(None, resolution.candidates)
    place_id = resolution.place_id
    existing = _find_duplicate(sb, place_id)
    if existing:
        raise DuplicateLead(existing)

    row, warnings = _fetch_and_map(place_id, language)
    photos = row.pop("_photos")
    row.pop("_enriched")
    row["lead_type"] = lead_type
    try:
        res = sb.table("leads").insert(row).execute()
    except Exception as e:  # noqa: BLE001 — unique violation raced the pre-check
        if _is_unique_violation(e):
            # the clash may be on external_id (e.g. a lead whose place ID was cleared)
            holder = _find_duplicate(sb, place_id) or _find_by_external_id(sb, place_id)
            if holder:
                raise DuplicateLead(holder) from e
        raise
    if not res.data:
        raise RuntimeError("Insert failed")
    lead = res.data[0]
    row["_photos"] = photos
    try:
        photo_patch, photo_warnings = _attach_photos(sb, lead["id"], row, row["extra"])
        photo_patch["extra"] = _with_warnings(photo_patch["extra"], warnings + photo_warnings)
        upd = sb.table("leads").update(photo_patch).eq("id", lead["id"]).execute()
        lead = (upd.data or [lead])[0]
    except Exception as e:  # noqa: BLE001 — the lead exists; don't lose it over photos
        logger.exception("lead %s: photo write-back failed", lead["id"])
        return ImportOutcome(lead, [], warnings + [f"photos not saved: {type(e).__name__}"])
    return ImportOutcome(lead, [], warnings + photo_warnings)


def reimport_place(
    sb, current: dict, *, raw_input: str | None, overwrite: bool, language: str
) -> ImportOutcome:
    if raw_input:
        _consume_if_text(raw_input)
        resolution = resolve(raw_input, language=language)
        if resolution.place_id is None:
            return ImportOutcome(None, resolution.candidates)
        place_id = resolution.place_id
        if place_id != current.get("google_place_id"):
            other = _find_duplicate(sb, place_id)
            if other and other != current["id"]:
                raise DuplicateLead(other)
    elif current.get("google_place_id"):
        place_id = current["google_place_id"]
    else:
        raise MissingPlaceId(
            "This lead has no Google place ID; paste a Google Maps link to import."
        )

    row, warnings = _fetch_and_map(place_id, language)
    enriched = row.pop("_enriched")
    if overwrite:
        photo_patch, photo_warnings = _attach_photos(sb, current["id"], row, row["extra"])
        patch = {k: v for k, v in row.items() if k in GOOGLE_FIELDS}
        patch.update(photo_patch)
        # keep non-Google keys of extra (e.g. legacy scraper data)
        patch["extra"] = {**(current.get("extra") or {}), **patch["extra"]}
        if not enriched:
            # No website data this time: keep what the lead has, except a social
            # link that Google itself listed as the website.
            for key in ("email", "social_links", "facebook_url", "instagram_url", "description"):
                patch.pop(key, None)
            listed = {
                platform: row[col]
                for col, platform in (("facebook_url", "facebook"), ("instagram_url", "instagram"))
                if row.get(col)
            }
            if listed:
                links = {**(current.get("social_links") or {}), **listed}
                patch["social_links"] = links
                patch["facebook_url"] = links.get("facebook")
                patch["instagram_url"] = links.get("instagram")
    elif current.get("photo_urls"):
        row.pop("_photos")
        patch = merge_fill_empty(current, row)
        patch["photo_urls"] = list(current.get("photo_urls") or [])
        google = dict(patch["extra"].get("google") or {})
        google["photos"] = list(
            ((current.get("extra") or {}).get("google") or {}).get("photos") or []
        )
        patch["extra"]["google"] = google
        photo_warnings = []
    else:
        # fill-empty with no photos yet: photos are an empty field too
        photo_patch, photo_warnings = _attach_photos(sb, current["id"], row, row["extra"])
        patch = merge_fill_empty(current, row)
        patch["photo_urls"] = photo_patch["photo_urls"]
        patch["extra"]["google"] = photo_patch["extra"]["google"]
    patch.pop("external_id", None)
    patch.pop("primary_source", None)
    warnings = warnings + photo_warnings
    patch["extra"] = _with_warnings(patch["extra"], warnings)
    try:
        res = sb.table("leads").update(patch).eq("id", current["id"]).execute()
    except Exception as e:  # noqa: BLE001 — another lead already holds this place ID
        if _is_unique_violation(e):
            other = _find_duplicate(sb, place_id)
            if other:
                raise DuplicateLead(other) from e
        raise
    if not res.data:
        raise RuntimeError("Update failed")
    if overwrite:
        old = [u for u in (current.get("photo_urls") or []) if u not in patch["photo_urls"]]
        try:
            delete_lead_photos(sb, current["id"], old)
        except Exception as e:  # noqa: BLE001 — new row is saved; stale files are harmless
            warnings.append(f"old photo cleanup failed: {type(e).__name__}")
    return ImportOutcome(res.data[0], [], warnings)
