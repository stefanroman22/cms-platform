"""Turn whatever the admin pastes into a place ID (ADR-0012).

Order: raw place ID -> ID embedded in the URL -> Maps Tools Resolution API ($0) ->
Text Search on the name/coords parsed out of the (expanded) URL -> candidates for the
admin to pick. Free text goes straight to Text Search."""

from __future__ import annotations

import re
import urllib.parse
import urllib.request
from dataclasses import dataclass, field

from . import client

PLACE_ID_RE = re.compile(r"^(?=.*[A-Z])(?=.*[a-z])[A-Za-z0-9_-]{20,}$")
_QUERY_ID_RE = re.compile(r"[?&](?:query_place_id|place_id|placeid)=([A-Za-z0-9_-]{20,})")
_DATA_ID_RE = re.compile(r"!19s(ChIJ[A-Za-z0-9_-]+)")
_PLACE_PATH_RE = re.compile(r"/maps/place/([^/@?]+)(?:/@(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?))?")
_MAPS_HOST_RE = re.compile(
    r"^(?:www\.|maps\.)?(?:google\.(?:com|[a-z]{2}|com?\.[a-z]{2})|goo\.gl|maps\.app\.goo\.gl|g\.page|g\.co)$"
)
_SHORTENER_HOST_RE = re.compile(r"^(?:www\.)?(?:goo\.gl|maps\.app\.goo\.gl|g\.page|g\.co)$")


@dataclass
class Resolution:
    place_id: str | None
    candidates: list[dict] = field(default_factory=list)


def _hostname(url: str) -> str:
    try:
        return (urllib.parse.urlsplit(url).hostname or "").lower()
    except ValueError:
        return ""


def classify(raw: str) -> tuple[str, str]:
    value = raw.strip()
    if PLACE_ID_RE.match(value):
        return "place_id", value
    if "://" not in value and value.lower().startswith(
        ("maps.app.goo.gl", "goo.gl", "www.google.", "maps.google.")
    ):
        value = "https://" + value
    host = _hostname(value)
    if host and _MAPS_HOST_RE.match(host):
        return "maps_url", value
    return "text", value


def extract_place_id_from_url(url: str) -> str | None:
    m = _QUERY_ID_RE.search(url) or _DATA_ID_RE.search(url)
    return m.group(1) if m else None


def parse_name_and_coords(url: str) -> tuple[str | None, float | None, float | None]:
    m = _PLACE_PATH_RE.search(url)
    if not m:
        return None, None, None
    name = urllib.parse.unquote_plus(m.group(1)).strip() or None
    lat = float(m.group(2)) if m.group(2) else None
    lng = float(m.group(3)) if m.group(3) else None
    return name, lat, lng


def expand_short_link(url: str) -> str:
    """Follow redirects of a goo.gl-style link; return the final URL (or the input)."""
    req = urllib.request.Request(url, headers={"User-Agent": client.USER_AGENT}, method="GET")
    try:
        with client._urlopen(req, 8) as resp:
            return resp.geturl() or url
    except Exception:  # noqa: BLE001 — any failure just means "no expansion"
        return url


def resolve(raw: str, *, language: str = "en") -> Resolution:
    kind, value = classify(raw)
    if kind == "place_id":
        return Resolution(value)

    if kind == "maps_url":
        embedded = extract_place_id_from_url(value)
        if embedded:
            return Resolution(embedded)
        pid = client.resolve_maps_url(value)
        if pid:
            return Resolution(pid)
        expanded = expand_short_link(value) if _SHORTENER_HOST_RE.match(_hostname(value)) else value
        embedded = extract_place_id_from_url(expanded)
        if embedded:
            return Resolution(embedded)
        name, lat, lng = parse_name_and_coords(expanded)
        if not name:
            return Resolution(None)
        return _from_search(client.text_search(name, lat=lat, lng=lng, language=language))

    return _from_search(client.text_search(value, language=language))


def _from_search(hits: list[dict]) -> Resolution:
    if len(hits) == 1:
        return Resolution(hits[0]["place_id"])
    return Resolution(None, hits)
