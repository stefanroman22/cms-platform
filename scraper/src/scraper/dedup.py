"""Pure helpers — no IO. Easy to unit-test, kept apart from playwright."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from urllib.parse import urlparse

_SOCIAL_DOMAINS: frozenset[str] = frozenset(
    {
        "facebook.com",
        "fb.com",
        "m.facebook.com",
        "instagram.com",
        "linktr.ee",
        "linktree.com",
        "beacons.ai",
        "tiktok.com",
        "x.com",
        "twitter.com",
    }
)
_FEATURE_ID_RE = re.compile(r"!1s(0x[0-9a-f]+:0x[0-9a-f]+)", re.IGNORECASE)
# Latitude + longitude in Google Maps place URLs: `!3d{lat}!4d{lng}`.
_LATLNG_RE = re.compile(r"!3d(-?\d+\.\d+)!4d(-?\d+\.\d+)")


def peek_external_id(url: str) -> str | None:
    """Cheap pre-visit check — returns the Google feature id if the URL
    already encodes one. Lets the engine drop duplicate links BEFORE
    paying the cost of a place-page visit. Returns None when the URL
    lacks the canonical `!1s0x...:0x...` segment; the caller then has
    to visit the page and use external_id_from_url for the hash fallback."""
    m = _FEATURE_ID_RE.search(url)
    return m.group(1) if m else None


def parse_latlng_from_url(url: str) -> tuple[float | None, float | None]:
    """Pull `(lat, lng)` out of a Google Maps place URL containing
    `!3d{lat}!4d{lng}`. Returns (None, None) when the segment is absent."""
    m = _LATLNG_RE.search(url)
    if not m:
        return None, None
    try:
        return float(m.group(1)), float(m.group(2))
    except ValueError:
        return None, None


def normalize_name(name: str) -> str:
    """Lower-case, strip diacritics + punctuation, collapse whitespace."""
    if not name:
        return ""
    decomposed = unicodedata.normalize("NFKD", name)
    no_diacritics = "".join(c for c in decomposed if not unicodedata.combining(c))
    lowered = no_diacritics.lower()
    no_punct = re.sub(r"[^\w\s]", " ", lowered)
    collapsed = re.sub(r"\s+", " ", no_punct).strip()
    return collapsed


def external_id_from_url(
    url: str,
    *,
    normalized_name: str | None = None,
    city: str | None = None,
    lat: float | None = None,
    lng: float | None = None,
) -> str:
    """Prefer Google's stable feature id (encoded in the place URL).
    Fall back to a hash of (normalized_name, city, rounded coords) so a
    re-scrape still dedups. Last-ditch: hash the URL itself."""
    m = _FEATURE_ID_RE.search(url)
    if m:
        return m.group(1)

    if not normalized_name:
        return "hash:" + hashlib.sha256(url.encode()).hexdigest()[:24]

    lat_str = f"{lat:.4f}" if lat is not None else ""
    lng_str = f"{lng:.4f}" if lng is not None else ""
    payload = f"{normalized_name}|{city or ''}|{lat_str}|{lng_str}"
    return "hash:" + hashlib.sha256(payload.encode()).hexdigest()[:24]


def classify_web_presence(
    website_url: str | None,
) -> tuple[str, str | None, str | None]:
    """Return (web_presence, facebook_url, instagram_url) given the URL
    Google Maps surfaces as the place's "website" link."""
    if not website_url:
        return "none", None, None

    host = (urlparse(website_url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    if host in _SOCIAL_DOMAINS:
        fb = website_url if ("facebook" in host or host == "fb.com") else None
        ig = website_url if "instagram" in host else None
        return "social_only", fb, ig

    return "has_website", None, None
