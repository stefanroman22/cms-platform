#!/usr/bin/env python3
"""
validate-lead.py — Validate and normalize a lead JSON record before prompt generation.

Usage:
    python validate-lead.py < lead.json
    python validate-lead.py lead.json
    cat lead.json | python validate-lead.py

Output:
    On success: normalized JSON to stdout, exit 0.
    On failure: errors to stderr, exit 1.

Behavior:
    - Required fields: business_name, category (must be non-empty strings)
    - Placeholders ('Not found', 'N/A', '-', '', 'null', 'None') become None
    - Country codes (NL, BE, DE, FR) expand to full names alongside the code
    - lat/lng must both be present or both absent — if only one, both become None
    - rating must be 0–5 if present
    - review_count must be a non-negative integer if present
    - opening_hours keys normalized to Mon/Tue/Wed/Thu/Fri/Sat/Sun
    - URLs lightly sanity-checked (must start with http or https)
    - Warnings (not failures) printed to stderr for low-quality fields

This script is intentionally permissive — most fields are optional. It exists to
catch malformed inputs early, not to enforce a rigid schema.
"""

import json
import sys
from typing import Any

PLACEHOLDER_STRINGS = {
    "",
    "not found",
    "n/a",
    "na",
    "-",
    "—",
    "null",
    "none",
    "undefined",
    "no data",
    "tbd",
    "to be determined",
    "?",
    "??",
    "???",
}

COUNTRY_CODE_MAP = {
    "NL": "Netherlands",
    "BE": "Belgium",
    "DE": "Germany",
    "FR": "France",
    "ES": "Spain",
    "IT": "Italy",
    "PT": "Portugal",
    "AT": "Austria",
    "CH": "Switzerland",
    "DK": "Denmark",
    "SE": "Sweden",
    "NO": "Norway",
    "FI": "Finland",
    "PL": "Poland",
    "CZ": "Czechia",
    "UK": "United Kingdom",
    "GB": "United Kingdom",
    "IE": "Ireland",
    "US": "United States",
}

DAY_NORMALIZATION = {
    "mon": "Mon",
    "monday": "Mon",
    "maandag": "Mon",
    "tue": "Tue",
    "tuesday": "Tue",
    "dinsdag": "Tue",
    "wed": "Wed",
    "wednesday": "Wed",
    "woensdag": "Wed",
    "thu": "Thu",
    "thursday": "Thu",
    "donderdag": "Thu",
    "fri": "Fri",
    "friday": "Fri",
    "vrijdag": "Fri",
    "sat": "Sat",
    "saturday": "Sat",
    "zaterdag": "Sat",
    "sun": "Sun",
    "sunday": "Sun",
    "zondag": "Sun",
}

# These string values get passed through as-is (used by hours fields)
PASSTHROUGH_VALUES = {"closed", "gesloten", "by appointment only", "24/7", "24 hours"}


def is_placeholder(value: Any) -> bool:
    """Return True if value is a recognized placeholder string."""
    if value is None:
        return True
    if isinstance(value, str):
        return value.strip().lower() in PLACEHOLDER_STRINGS
    return False


def strip_placeholders(obj: Any) -> Any:
    """Recursively replace placeholder strings with None."""
    if is_placeholder(obj):
        return None
    if isinstance(obj, dict):
        return {k: strip_placeholders(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [strip_placeholders(item) for item in obj]
    if isinstance(obj, str):
        return obj.strip()
    return obj


def normalize_country(lead: dict) -> None:
    """Expand 2-letter country codes to full names; keep the code too."""
    country = lead.get("country")
    if isinstance(country, str) and len(country.strip()) == 2:
        code = country.strip().upper()
        if code in COUNTRY_CODE_MAP:
            lead["country_code"] = code
            lead["country"] = COUNTRY_CODE_MAP[code]


def normalize_hours(lead: dict) -> None:
    """Normalize opening_hours day keys (e.g. 'monday' -> 'Mon')."""
    hours = lead.get("opening_hours")
    if not isinstance(hours, dict):
        return
    normalized = {}
    for key, value in hours.items():
        if not isinstance(key, str):
            normalized[key] = value
            continue
        canon = DAY_NORMALIZATION.get(key.strip().lower(), key)
        normalized[canon] = value
    lead["opening_hours"] = normalized


def validate(lead: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings). Empty errors list means valid."""
    errors: list[str] = []
    warnings: list[str] = []

    # Required fields
    if not lead.get("business_name"):
        errors.append("Required field missing or empty: business_name")
    if not lead.get("category"):
        errors.append("Required field missing or empty: category")

    # Type checks
    rating = lead.get("rating")
    if rating is not None:
        if not isinstance(rating, int | float) or not (0 <= rating <= 5):
            errors.append(f"rating must be a number 0-5, got {rating!r}")

    review_count = lead.get("review_count")
    if review_count is not None:
        if not isinstance(review_count, int) or review_count < 0:
            errors.append(f"review_count must be a non-negative integer, got {review_count!r}")

    # Coordinates: both or neither
    lat, lng = lead.get("lat"), lead.get("lng")
    if (lat is None) != (lng is None):
        warnings.append(
            "lat/lng partially specified — both will be treated as null "
            "(map embed will be skipped)"
        )
        lead["lat"] = None
        lead["lng"] = None
    elif lat is not None:
        if not isinstance(lat, int | float) or not (-90 <= lat <= 90):
            errors.append(f"lat out of range -90..90: {lat!r}")
        if not isinstance(lng, int | float) or not (-180 <= lng <= 180):
            errors.append(f"lng out of range -180..180: {lng!r}")

    # URL sanity checks
    for url_field in ("website_url", "facebook_url", "instagram_url", "menu_url", "source_url"):
        val = lead.get(url_field)
        if val is not None and isinstance(val, str):
            if not (val.startswith("http://") or val.startswith("https://")):
                warnings.append(f"{url_field} doesn't start with http(s)://: {val!r}")

    # Quality warnings
    if lead.get("rating") is not None and lead.get("review_count") is not None:
        if lead["review_count"] < 5:
            warnings.append(
                f"review_count={lead['review_count']} is low — trust band will be suppressed"
            )
        elif lead["rating"] < 4.0:
            warnings.append(f"rating={lead['rating']} is below 4.0 — trust band will be suppressed")

    if not lead.get("design_prompt"):
        warnings.append(
            "No design_prompt provided — output will fall back entirely to category defaults. "
            "Consider asking the business owner for a one-paragraph brief."
        )

    if lead.get("web_presence") not in (None, "none", "social_only", "outdated", "ok"):
        warnings.append(
            f"web_presence={lead.get('web_presence')!r} is non-standard "
            "(expected: none, social_only, outdated, ok)"
        )

    return errors, warnings


def main() -> int:
    # Read input
    if len(sys.argv) > 1:
        try:
            with open(sys.argv[1]) as f:
                raw = json.load(f)
        except FileNotFoundError:
            print(f"File not found: {sys.argv[1]}", file=sys.stderr)
            return 1
        except json.JSONDecodeError as e:
            print(f"Invalid JSON in {sys.argv[1]}: {e}", file=sys.stderr)
            return 1
    else:
        try:
            raw = json.load(sys.stdin)
        except json.JSONDecodeError as e:
            print(f"Invalid JSON on stdin: {e}", file=sys.stderr)
            return 1

    if not isinstance(raw, dict):
        print(f"Lead must be a JSON object, got {type(raw).__name__}", file=sys.stderr)
        return 1

    # Normalize
    lead = strip_placeholders(raw)
    normalize_country(lead)
    normalize_hours(lead)

    # Validate
    errors, warnings = validate(lead)

    # Report warnings to stderr regardless
    for w in warnings:
        print(f"WARN: {w}", file=sys.stderr)

    # On errors, exit non-zero
    if errors:
        for e in errors:
            print(f"ERROR: {e}", file=sys.stderr)
        return 1

    # Success — emit normalized lead
    json.dump(lead, sys.stdout, indent=2, ensure_ascii=False)
    print()  # trailing newline
    return 0


if __name__ == "__main__":
    sys.exit(main())
