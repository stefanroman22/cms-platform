"""Pure + mocked tests for scraper.geo. No live Nominatim."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

import scraper.geo as geo
from scraper.geo import bbox_for_place, grid_centers


def test_grid_centers_count_for_known_box():
    # ~5 km lat span × ~5 km lng span at ~52°N → roughly a 5×5 grid at 1 km.
    centers = list(grid_centers(52.0, 5.0, 52.045, 5.073, cell_km=1.0))
    assert 20 <= len(centers) <= 30


def test_grid_centers_all_inside_bbox():
    box = (52.0, 5.0, 52.05, 5.08)
    for lat, lng in grid_centers(*box, cell_km=1.0):
        assert 52.0 <= lat <= 52.05
        assert 5.0 <= lng <= 5.08


def test_grid_centers_longitude_spacing_widens_with_latitude():
    low = list(grid_centers(0.0, 0.0, 0.005, 0.2, cell_km=1.0))
    high = list(grid_centers(60.0, 0.0, 60.005, 0.2, cell_km=1.0))
    assert len(high) < len(low)  # wider lng steps near the pole → fewer columns


def test_grid_centers_subcell_bbox_yields_at_least_one():
    # A bbox far smaller than a cell must still yield one (midpoint) center —
    # never an empty grid, which would silently scrape nothing.
    centers = list(grid_centers(52.0, 5.0, 52.0009, 5.0009, cell_km=1.2))
    assert len(centers) == 1
    lat, lng = centers[0]
    assert 52.0 <= lat <= 52.0009
    assert 5.0 <= lng <= 5.0009


def _fake_resp():
    r = MagicMock()
    r.__enter__ = MagicMock(return_value=r)
    r.__exit__ = MagicMock(return_value=None)
    return r


def test_bbox_for_place_parses_south_north_west_east(monkeypatch):
    geo._GEO_CACHE.clear()
    payload = [{"boundingbox": ["52.45", "52.55", "5.40", "5.50"]}]  # [s, n, w, e]
    monkeypatch.setattr(geo.time, "sleep", lambda _s: None)
    with (
        patch.object(geo.json, "load", return_value=payload),
        patch.object(geo.urllib.request, "urlopen", return_value=_fake_resp()) as mock_open,
    ):
        box = bbox_for_place("Lelystad")
    assert box == (52.45, 5.40, 52.55, 5.50)  # (min_lat, min_lng, max_lat, max_lng)
    assert mock_open.call_count == 1


def test_bbox_for_place_caches_second_call(monkeypatch):
    geo._GEO_CACHE.clear()
    payload = [{"boundingbox": ["1.0", "2.0", "3.0", "4.0"]}]
    monkeypatch.setattr(geo.time, "sleep", lambda _s: None)
    with (
        patch.object(geo.json, "load", return_value=payload),
        patch.object(geo.urllib.request, "urlopen", return_value=_fake_resp()) as mock_open,
    ):
        bbox_for_place("Almere")
        bbox_for_place("Almere")
    assert mock_open.call_count == 1  # second call served from cache


def test_bbox_for_place_empty_result_raises(monkeypatch):
    geo._GEO_CACHE.clear()
    monkeypatch.setattr(geo.time, "sleep", lambda _s: None)
    with (
        patch.object(geo.json, "load", return_value=[]),
        patch.object(geo.urllib.request, "urlopen", return_value=_fake_resp()),
    ):
        with pytest.raises(ValueError, match="no geocoding result"):
            bbox_for_place("Nowhereville")


def test_bbox_for_place_disk_cache_roundtrip(tmp_path, monkeypatch):
    geo._GEO_CACHE.clear()
    cache = tmp_path / "geo.json"
    payload = [{"boundingbox": ["52.45", "52.55", "5.40", "5.50"]}]
    monkeypatch.setattr(geo.time, "sleep", lambda _s: None)
    with (
        patch.object(geo.json, "load", return_value=payload),
        patch.object(geo.urllib.request, "urlopen", return_value=_fake_resp()) as mock_open,
    ):
        box1 = bbox_for_place("Lelystad", cache_path=cache)
    assert mock_open.call_count == 1
    assert cache.exists()  # write-through persisted the box

    # Simulate a fresh process: drop the in-memory cache; the disk file must
    # serve the second call WITHOUT re-hitting Nominatim.
    geo._GEO_CACHE.clear()
    with (
        patch.object(geo.json, "load", return_value=payload),
        patch.object(geo.urllib.request, "urlopen", return_value=_fake_resp()) as mock_open2,
    ):
        box2 = bbox_for_place("Lelystad", cache_path=cache)
    assert mock_open2.call_count == 0
    assert box1 == box2 == (52.45, 5.40, 52.55, 5.50)


def test_split_cell_yields_four_distinct_quarter_centers():
    from scraper.geo import split_cell

    subs = list(split_cell(52.0, 5.0, 1.2))
    assert len(subs) == 4
    assert len(set(subs)) == 4  # distinct
    for lat, lng in subs:  # each within ~±cell_km/4 of the parent centre
        assert abs(lat - 52.0) < 0.004
        assert abs(lng - 5.0) < 0.006
    lats = sorted({lat for lat, _ in subs})
    assert len(lats) == 2 and lats[0] < 52.0 < lats[1]  # two below, two above
