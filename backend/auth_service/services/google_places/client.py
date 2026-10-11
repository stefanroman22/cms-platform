"""Thin urllib client for Places API (New), Place Photos and the Maps Tools Resolution
API (ADR-0012). One function per Google call; no SDK, no retries, 10 s timeouts.
Every failure surfaces as GooglePlacesError(status, message) so the router can map it."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from ...core.config import settings

USER_AGENT = "roman-technologies-cms-backend/1.0"
PLACES_BASE = "https://places.googleapis.com/v1"
RESOLVE_URL = "https://mapstools.googleapis.com/v1:resolveMapsUrls"

# Everything Place Details (New) exposes that a lead can use. Requesting any
# Enterprise + Atmosphere field bills the whole call at that SKU, so one call
# fetches it all. Keep it a single comma-separated string with no spaces.
PLACE_FIELD_MASK = ",".join(
    [
        "id",
        "displayName",
        "primaryType",
        "primaryTypeDisplayName",
        "types",
        "businessStatus",
        "googleMapsUri",
        "googleMapsLinks",
        "formattedAddress",
        "shortFormattedAddress",
        "addressComponents",
        "postalAddress",
        "location",
        "plusCode",
        "viewport",
        "timeZone",
        "utcOffsetMinutes",
        "pureServiceAreaBusiness",
        "nationalPhoneNumber",
        "internationalPhoneNumber",
        "websiteUri",
        "regularOpeningHours",
        "regularSecondaryOpeningHours",
        "rating",
        "userRatingCount",
        "reviews",
        "reviewSummary",
        "editorialSummary",
        "generativeSummary",
        "neighborhoodSummary",
        "priceLevel",
        "priceRange",
        "photos",
        "accessibilityOptions",
        "parkingOptions",
        "paymentOptions",
        "dineIn",
        "takeout",
        "delivery",
        "curbsidePickup",
        "reservable",
        "outdoorSeating",
        "liveMusic",
        "restroom",
        "goodForChildren",
        "goodForGroups",
        "goodForWatchingSports",
        "allowsDogs",
        "menuForChildren",
        "servesBreakfast",
        "servesBrunch",
        "servesLunch",
        "servesDinner",
        "servesBeer",
        "servesWine",
        "servesCocktails",
        "servesCoffee",
        "servesDessert",
        "servesVegetarianFood",
    ]
)
TEXT_SEARCH_MASK = "places.id,places.displayName,places.formattedAddress"


class GooglePlacesError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(f"{status}: {message}")
        self.status = status
        self.message = message


def _api_key() -> str:
    key = settings.GOOGLE_MAPS_API_KEY
    if not key:
        raise GooglePlacesError(503, "Google Maps import is not configured on this backend")
    return key


def _urlopen(req: urllib.request.Request, timeout: int):
    """Single seam for tests to patch."""
    return urllib.request.urlopen(req, timeout=timeout)


def _google_message(raw: str) -> str:
    try:
        err = json.loads(raw).get("error") or {}
        return str(err.get("message") or err.get("status") or raw)[:500]
    except (ValueError, AttributeError):
        return raw[:500]


def _request_json(
    url: str,
    *,
    method: str = "GET",
    body: dict | None = None,
    field_mask: str | None = None,
    timeout: int = 10,
) -> dict:
    headers = {"X-Goog-Api-Key": _api_key(), "User-Agent": USER_AGENT, "Accept": "application/json"}
    if field_mask:
        headers["X-Goog-FieldMask"] = field_mask
    data = None
    if body is not None:
        data = json.dumps(body).encode()
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with _urlopen(req, timeout) as resp:
            return json.loads(resp.read().decode() or "{}")
    except urllib.error.HTTPError as e:
        raise GooglePlacesError(e.code, _google_message(e.read().decode(errors="replace"))) from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise GooglePlacesError(504, f"Google request failed: {e}") from e


def place_details(place_id: str, *, language: str = "en") -> dict:
    qs = urllib.parse.urlencode({"languageCode": language})
    return _request_json(
        f"{PLACES_BASE}/places/{urllib.parse.quote(place_id, safe='')}?{qs}",
        field_mask=PLACE_FIELD_MASK,
    )


def resolve_maps_url(url: str) -> str | None:
    """maps.app.goo.gl / google.com/maps/place URL -> place ID, or None if Google can't."""
    data = _request_json(RESOLVE_URL, method="POST", body={"urls": [url]})
    entities = data.get("entities") or [{}]
    raw = (entities[0] or {}).get("placeId") or (entities[0] or {}).get("name") or ""
    return raw.removeprefix("places/") or None


def text_search(
    query: str,
    *,
    lat: float | None = None,
    lng: float | None = None,
    language: str = "en",
    page_size: int = 5,
) -> list[dict]:
    body: dict = {"textQuery": query, "pageSize": page_size, "languageCode": language}
    if lat is not None and lng is not None:
        body["locationBias"] = {
            "circle": {"center": {"latitude": lat, "longitude": lng}, "radius": 2000.0}
        }
    data = _request_json(
        f"{PLACES_BASE}/places:searchText", method="POST", body=body, field_mask=TEXT_SEARCH_MASK
    )
    out = []
    for p in data.get("places") or []:
        if not p.get("id"):
            continue
        out.append(
            {
                "place_id": p["id"],
                "name": (p.get("displayName") or {}).get("text"),
                "address": p.get("formattedAddress"),
            }
        )
    return out


def photo_uri(photo_name: str, *, max_width_px: int = 1600) -> str:
    """Resolve a photo resource name to a short-lived googleusercontent URL."""
    data = _request_json(
        f"{PLACES_BASE}/{photo_name}/media?maxWidthPx={max_width_px}&skipHttpRedirect=true"
    )
    uri = data.get("photoUri")
    if not uri:
        raise GooglePlacesError(502, "Place Photos returned no photoUri")
    return uri


def fetch_bytes(url: str, *, max_bytes: int = 8_000_000, timeout: int = 10) -> tuple[bytes, str]:
    """Download a public image (no API key header). Raises GooglePlacesError on size/HTTP."""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with _urlopen(req, timeout) as resp:
            ctype = (resp.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            body = resp.read(max_bytes + 1)
    except urllib.error.HTTPError as e:
        raise GooglePlacesError(e.code, f"photo download failed ({e.code})") from e
    except (urllib.error.URLError, TimeoutError) as e:
        raise GooglePlacesError(504, f"photo download failed: {e}") from e
    if len(body) > max_bytes:
        raise GooglePlacesError(413, f"photo larger than {max_bytes} bytes")
    return body, ctype
