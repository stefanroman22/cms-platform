"""URL helpers — validation + short-link expansion.

Separated from dedup.py because expand_if_short does HTTP IO and dedup.py
is intentionally IO-free."""

from __future__ import annotations

import urllib.request
from urllib.parse import urlparse

from .dedup import peek_external_id

_MAPS_HOST_SUFFIXES: frozenset[str] = frozenset(
    {
        "google.com",
        "maps.google.com",
        "maps.app.goo.gl",
        "goo.gl",
    }
)
_SHORT_HOSTS: frozenset[str] = frozenset({"maps.app.goo.gl", "goo.gl"})
_EXPAND_TIMEOUT_S = 8


class InvalidMapsURLError(ValueError):
    """Raised when a user-provided URL is not a usable Google Maps place URL."""


def is_google_maps_url(url: str) -> bool:
    """Cheap structural check — does this look like a Google Maps URL?

    Does NOT verify the URL points at a place (vs. a search page). Use
    expand_if_short() for that, which inspects the resolved URL.
    """
    if not url:
        return False
    try:
        parsed = urlparse(url)
    except ValueError:
        return False
    if parsed.scheme not in ("http", "https"):
        return False
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    if host in _MAPS_HOST_SUFFIXES:
        # google.com requires /maps in path; bare google.com is not a maps URL.
        if host == "google.com":
            return parsed.path.startswith("/maps")
        if host == "goo.gl":
            return parsed.path.startswith("/maps")
        return True
    return False


def expand_if_short(url: str) -> str:
    """Return the canonical Google Maps URL.

    - Full URLs (containing `/maps/place/` or the `!1s` feature-id segment)
      are returned unchanged.
    - Short URLs (`maps.app.goo.gl`, `goo.gl/maps/...`) are expanded by
      issuing a GET and reading the final URL via `response.geturl()`.
    - If the expanded URL is not a place page, raises InvalidMapsURLError.
    """
    if not is_google_maps_url(url):
        raise InvalidMapsURLError(f"not a Google Maps URL: {url!r}")

    parsed = urlparse(url)
    host = (parsed.hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]

    # Full URLs need no expansion, but still validate they're place pages.
    # Without this check a search URL like /maps/search/restaurants would
    # silently fail deep inside Playwright (no PLACE_TITLE) rather than here.
    if host not in _SHORT_HOSTS:
        if "/place/" not in url and "!1s" not in url:
            raise InvalidMapsURLError(
                f"URL is not a place page (expected /maps/place/... or !1s...): {url!r}"
            )
        return url

    # Short link — follow redirect.
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "rt-scraper/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=_EXPAND_TIMEOUT_S) as resp:
        final: str = resp.geturl()

    # After expansion, confirm we landed on a place page.
    if "/place/" not in final and "!1s" not in final:
        raise InvalidMapsURLError(f"short URL is not a place page (resolved to): {final!r}")
    return final


def canonicalize_place_url(url: str) -> str:
    """Rebuild a Google Maps place URL to the minimal canonical form that
    reliably loads the full Overview view.

    A URL copied from the reviews panel carries the '!1b1' view flag, which
    deep-links into a sub-view that renders WITHOUT the place title/address/
    website the scraper extracts. Naively trimming the data blob leaves it
    malformed, so Google renders an empty place skeleton (the <h1> exists but is
    empty). Rebuilding from the stable feature id (!1s0x..:0x..) yields a clean
    place URL that fully populates title/website/phone/address. Falls back to a
    query-stripped URL when no feature id is present."""
    fid = peek_external_id(url)
    if fid is None:
        return url.split("?", 1)[0]
    return f"https://www.google.com/maps/place//data=!4m2!3m1!1s{fid}"
