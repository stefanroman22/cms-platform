"""Geo helpers: bounding-box geocoding (Nominatim) + grid tiling.

grid_centers is pure and unit-tested; bbox_for_place does cached HTTP IO
(one request per region per run, honouring Nominatim's usage policy:
descriptive User-Agent, <=1 req/s, cached)."""

from __future__ import annotations

import json
import math
import time
import urllib.parse
import urllib.request
from collections.abc import Iterator
from pathlib import Path

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_USER_AGENT = "rt-scraper/1.0 (ops@romantech.example)"

# Process-level cache so repeated bbox_for_place(name) calls never re-hit
# Nominatim within a run; optional disk cache survives across runs.
_GEO_CACHE: dict[str, tuple[float, float, float, float]] = {}


def grid_centers(
    min_lat: float,
    min_lng: float,
    max_lat: float,
    max_lng: float,
    cell_km: float = 1.2,
) -> Iterator[tuple[float, float]]:
    """Yield (lat, lng) cell centres covering the bbox.

    Latitude step is ~constant (111 km/deg). Longitude step widens with
    latitude (meridians converge poleward) via cos(lat)."""
    dlat = cell_km / 111.0
    lat = min_lat + dlat / 2
    yielded = False
    while lat < max_lat:
        dlng = cell_km / (111.0 * math.cos(math.radians(lat)))
        lng = min_lng + dlng / 2
        while lng < max_lng:
            yield round(lat, 6), round(lng, 6)
            yielded = True
            lng += dlng
        lat += dlat
    if not yielded:
        # Sub-cell or degenerate bbox: one viewport at the midpoint still covers
        # it — never silently yield an empty grid (which would scrape nothing).
        yield round((min_lat + max_lat) / 2, 6), round((min_lng + max_lng) / 2, 6)


def split_cell(lat: float, lng: float, cell_km: float) -> Iterator[tuple[float, float]]:
    """Yield the 4 quarter-centres of a cell, each offset ±cell_km/4 from the
    parent centre. Used to subdivide a saturated cell at a tighter zoom."""
    dlat = (cell_km / 4) / 111.0
    dlng = (cell_km / 4) / (111.0 * math.cos(math.radians(lat)))
    for slat in (lat - dlat, lat + dlat):
        for slng in (lng - dlng, lng + dlng):
            yield round(slat, 6), round(slng, 6)


def _load_disk_cache(cache_path: Path) -> None:
    try:
        raw = json.loads(cache_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    for name, box in raw.items():
        if isinstance(box, list) and len(box) == 4:
            _GEO_CACHE[name] = (float(box[0]), float(box[1]), float(box[2]), float(box[3]))


def _save_disk_cache(cache_path: Path) -> None:
    try:
        cache_path.write_text(
            json.dumps({k: list(v) for k, v in _GEO_CACHE.items()}), encoding="utf-8"
        )
    except OSError:
        pass


def bbox_for_place(
    name: str, *, cache_path: Path | None = None
) -> tuple[float, float, float, float]:
    """Return (min_lat, min_lng, max_lat, max_lng) for a place name via Nominatim.

    Cached in-memory and (optionally) on disk. Raises ValueError when the
    geocoder returns no result."""
    if name in _GEO_CACHE:
        return _GEO_CACHE[name]
    if cache_path is not None:
        _load_disk_cache(cache_path)
        if name in _GEO_CACHE:
            return _GEO_CACHE[name]

    query = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
    req = urllib.request.Request(f"{_NOMINATIM}?{query}", headers={"User-Agent": _USER_AGENT})
    time.sleep(1.0)  # Nominatim policy: <=1 req/s
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.load(resp)

    if not data:
        raise ValueError(f"no geocoding result for {name!r}")

    bb = data[0]["boundingbox"]  # [south, north, west, east]
    box = (float(bb[0]), float(bb[2]), float(bb[1]), float(bb[3]))
    _GEO_CACHE[name] = box
    if cache_path is not None:
        _save_disk_cache(cache_path)
    return box
