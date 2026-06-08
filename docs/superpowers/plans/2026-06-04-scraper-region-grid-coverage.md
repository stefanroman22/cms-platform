# RT Scraper — Region-First Grid Coverage Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let the operator type only a place name and exhaustively scrape Google Maps leads via geographic grid tiling × category enumeration, breaking Google's ~120-per-search cap.

**Architecture:** Geocode the region once (Nominatim), tile its bbox into ~1.2 km cells, run one viewport-scoped (`@lat,lng,zoom`) bare-category query per cell × category, and reuse the existing per-place extraction / run-wide `external_id` dedup / filter / sink machinery unchanged. Phase 0 first greens the pre-existing mypy debt so the "mypy clean" gate is real.

**Tech Stack:** Python 3.11, Playwright (async), Pydantic v2, Typer, loguru, tenacity, pytest, mypy strict, ruff.

> **Commit gate (Stefan's standing rule):** Do NOT run `git commit` until Stefan explicitly says so. Keep `mypy src` and the full pytest suite green at every phase boundary; the commit commands below are the staged checkpoints to run *on his go-ahead*.

> **Run commands from `scraper/`** using the project venv:
> - tests: `./.venv/Scripts/python.exe -m pytest -q`
> - types: `./.venv/Scripts/python.exe -m mypy src`
> - lint:  `./.venv/Scripts/python.exe -m ruff check .`

---

## File Structure

**Phase 0 (mypy debt):**
- Modify: `src/scraper/urls.py` (annotate `geturl()` result)
- Modify: `src/scraper/models.py` (typed default-factory for `web_presence`)
- Modify: `src/scraper/cli.py` (`run_pending` JSON narrowing)

**Phase 1 (quick wins):**
- Modify: `src/scraper/models.py` (`min_reviews`→None, `max_results_per_area`→120)
- Modify: `src/scraper/selectors.py` (`RESULTS_END_TEXTS`)
- Modify: `src/scraper/google_maps.py` (`_text_has_end_sentinel`, `_feed_has_end_text`, harden `_collect_place_links`)
- Modify: `tests/test_models.py`, `tests/test_google_maps_pure.py`

**Phase 2 (grid):**
- Create: `src/scraper/geo.py` (grid tiling + geocoding)
- Create: `src/scraper/categories.py` (`DEFAULT_CATEGORIES`)
- Modify: `src/scraper/config.py` (`SCRAPER_GEOCODE_CACHE`)
- Modify: `src/scraper/models.py` (region/grid fields)
- Modify: `src/scraper/google_maps.py` (`GridTooLargeError`, viewport `_search_url`, `_build_grid_queries`, wire `scrape()`)
- Modify: `src/scraper/cli.py` (`--region/--bbox/--grid-*/--max-cells`, repeatable `--category`, new defaults)
- Create: `tests/test_geo.py`; Modify: `tests/test_google_maps_pure.py`, `tests/test_models.py`, `tests/test_cli.py`

---

## PHASE 0 — Green the mypy baseline

### Task 0.1: Fix `urls.py` Any-return

**Files:** Modify `src/scraper/urls.py:88`

- [ ] **Step 1: Run mypy to see the failure**

Run: `./.venv/Scripts/python.exe -m mypy src 2>&1 | grep urls`
Expected: `urls.py:93: error: Returning Any from function declared to return "str"`

- [ ] **Step 2: Annotate the result**

In `expand_if_short`, change line 88 from:
```python
        final = resp.geturl()
```
to:
```python
        final: str = resp.geturl()
```

- [ ] **Step 3: Verify mypy no longer flags urls.py**

Run: `./.venv/Scripts/python.exe -m mypy src 2>&1 | grep urls || echo "urls clean"`
Expected: `urls clean`

### Task 0.2: Fix `models.py` Field default-factory Literal inference

**Files:** Modify `src/scraper/models.py:25`

- [ ] **Step 1: Add a typed default-factory above `ScrapeFilters`**

Insert after the `WebPresence` type alias (after line 12) and before `class ScrapeFilters`:
```python
def _default_web_presence() -> list[WebPresence]:
    """Typed factory so mypy infers list[WebPresence], not list[str]."""
    return ["none", "social_only"]
```

- [ ] **Step 2: Use it in the field**

Change line 25 from:
```python
    web_presence: list[WebPresence] = Field(default_factory=lambda: ["none", "social_only"])
```
to:
```python
    web_presence: list[WebPresence] = Field(default_factory=_default_web_presence)
```

- [ ] **Step 3: Verify**

Run: `./.venv/Scripts/python.exe -m mypy src 2>&1 | grep models.py || echo "models clean"`
Expected: `models clean`

### Task 0.3: Fix `cli.py` `run_pending` JSON narrowing

**Files:** Modify `src/scraper/cli.py` (imports + lines ~165-166)

- [ ] **Step 1: Widen the typing import**

Change:
```python
from typing import Annotated
```
to:
```python
from typing import Annotated, Any, cast
```

- [ ] **Step 2: Cast the claimed row to a dict**

In `run_pending`, change:
```python
    job = rows[0]
    job_id = job["id"]
```
to:
```python
    job = cast(dict[str, Any], rows[0])
    job_id = job["id"]
```

- [ ] **Step 3: Verify the whole tree is mypy-clean**

Run: `./.venv/Scripts/python.exe -m mypy src`
Expected: `Success: no issues found in 13 source files`

- [ ] **Step 4: Verify ruff + full suite still green**

Run: `./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: ruff passes; `87 passed`

- [ ] **Step 5 (commit — on Stefan's go-ahead):**
```bash
git add scraper/src/scraper/urls.py scraper/src/scraper/models.py scraper/src/scraper/cli.py scraper/pyproject.toml
git commit -m "fix(scraper): green the mypy baseline (typed factory, geturl str, run_pending cast)"
```

---

## PHASE 1 — Quick wins

### Task 1.1: Flip the two default-asserting model tests (TDD red)

**Files:** Modify `tests/test_models.py`

- [ ] **Step 1: Update the assertions to the NEW required defaults**

In `test_scrape_params_default_construction_all_optional`, change:
```python
    assert p.max_results_per_area == 20
```
to:
```python
    assert p.max_results_per_area == 120
```
and change:
```python
    assert p.filters.min_reviews == 5
```
to:
```python
    assert p.filters.min_reviews is None
```

In `test_scrape_filters_all_optional_off_by_default`, change:
```python
    assert f.min_reviews == 5
```
to:
```python
    assert f.min_reviews is None
```

- [ ] **Step 2: Run them to verify they FAIL against the old defaults**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_models.py -q`
Expected: FAIL — `assert 20 == 120` / `assert 5 is None`

### Task 1.2: Change the model defaults (TDD green)

**Files:** Modify `src/scraper/models.py:23,38`

- [ ] **Step 1: Drop the review floor**

Change:
```python
    min_reviews: int | None = 5
```
to:
```python
    min_reviews: int | None = None
```

- [ ] **Step 2: Raise the per-query cap**

Change:
```python
    max_results_per_area: int = 20
```
to:
```python
    max_results_per_area: int = 120
```

- [ ] **Step 3: Verify model tests pass**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_models.py -q`
Expected: PASS

### Task 1.3: End-of-list sentinel text + pure matcher (TDD)

**Files:** Modify `src/scraper/selectors.py`; Modify `src/scraper/google_maps.py`; Modify `tests/test_google_maps_pure.py`

- [ ] **Step 1: Write the failing unit test** in `tests/test_google_maps_pure.py` (append):
```python
def test_text_has_end_sentinel_matches_known_phrases():
    from scraper.google_maps import _text_has_end_sentinel

    assert _text_has_end_sentinel("You've reached the end of the list.") is True
    assert _text_has_end_sentinel("foo Je hebt het EINDE van de lijst bereikt bar") is True
    assert _text_has_end_sentinel("ENDE DER LISTE") is True
    assert _text_has_end_sentinel("more results loading") is False
    assert _text_has_end_sentinel("") is False
```

- [ ] **Step 2: Run it — expect ImportError/fail**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_google_maps_pure.py::test_text_has_end_sentinel_matches_known_phrases -q`
Expected: FAIL — cannot import `_text_has_end_sentinel`

- [ ] **Step 3: Add the sentinels to `selectors.py`** (after the `RESULTS_END_MARKER` line, ~line 33):
```python
# End-of-list sentinel TEXT (obfuscated classes drift; match visible text too).
# Lowercased for case-insensitive `contains` checks.
RESULTS_END_TEXTS: tuple[str, ...] = (
    "you've reached the end of the list",
    "je hebt het einde van de lijst bereikt",  # nl
    "ende der liste",  # de
)
```

- [ ] **Step 4: Add the pure matcher to `google_maps.py`** (near `_collect_place_links`, above it):
```python
def _text_has_end_sentinel(text: str) -> bool:
    """True if `text` contains any end-of-list sentinel (case-insensitive)."""
    low = text.lower()
    return any(sentinel in low for sentinel in selectors.RESULTS_END_TEXTS)
```

- [ ] **Step 5: Run the unit test — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_google_maps_pure.py::test_text_has_end_sentinel_matches_known_phrases -q`
Expected: PASS

### Task 1.4: Harden `_collect_place_links` + add `_feed_has_end_text`

**Files:** Modify `src/scraper/google_maps.py:91-134`

- [ ] **Step 1: Add the async end-text helper** (immediately after `_text_has_end_sentinel`):
```python
async def _feed_has_end_text(page: Page) -> bool:
    """Read the results feed's text and check for an end-of-list sentinel.
    Complements the fragile obfuscated end-marker class."""
    try:
        feed = page.locator(selectors.RESULTS_FEED)
        if await feed.count() == 0:
            return False
        return _text_has_end_sentinel(await feed.inner_text())
    except Exception:
        return False
```

- [ ] **Step 2: Replace the scroll loop body** in `_collect_place_links`. Change the `while` header from:
```python
    while len(links) < max_results and stable_rounds < 3:
```
to:
```python
    while len(links) < max_results and stable_rounds < 5:
```
Change the end-marker check from:
```python
        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0:
            logger.debug("reached end-of-list marker")
            break
```
to:
```python
        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0 or await _feed_has_end_text(page):
            logger.debug("reached end-of-list marker")
            break
```
Change the scroll step from:
```python
        await feed.evaluate("(el) => el.scrollBy(0, el.scrollHeight)")
```
to:
```python
        await feed.evaluate("(el) => el.scrollBy(0, Math.floor(el.clientHeight * 0.8))")
```

- [ ] **Step 3: Verify types + full suite green**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; ruff clean; all tests PASS (88+ now)

- [ ] **Step 4 (commit — on Stefan's go-ahead):**
```bash
git add scraper/src/scraper/models.py scraper/src/scraper/selectors.py scraper/src/scraper/google_maps.py scraper/tests/test_models.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): raise per-query cap, drop default review floor, sturdier feed scroll"
```

---

## PHASE 2 — Region-first grid

### Task 2.1: `geo.py` — pure grid tiling (TDD)

**Files:** Create `src/scraper/geo.py`; Create `tests/test_geo.py`

- [ ] **Step 1: Write the failing pure tests** — `tests/test_geo.py`:
```python
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
```

- [ ] **Step 2: Run — expect ImportError**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_geo.py -q`
Expected: FAIL — no module `scraper.geo`

- [ ] **Step 3: Create `src/scraper/geo.py`** (grid math only for now; geocoding added in Task 2.2):
```python
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
    while lat < max_lat:
        dlng = cell_km / (111.0 * math.cos(math.radians(lat)))
        lng = min_lng + dlng / 2
        while lng < max_lng:
            yield round(lat, 6), round(lng, 6)
            lng += dlng
        lat += dlat


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
```

- [ ] **Step 4: Run the grid tests — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_geo.py -q`
Expected: PASS (3 tests)

### Task 2.2: `geo.py` — mocked geocoding tests

**Files:** Modify `tests/test_geo.py`

- [ ] **Step 1: Append the mocked-HTTP tests:**
```python
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
```

- [ ] **Step 2: Run — expect PASS** (geo.py already implements geocoding from Task 2.1)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_geo.py -q`
Expected: PASS (6 tests)

### Task 2.3: `categories.py`

**Files:** Create `src/scraper/categories.py`

- [ ] **Step 1: Create the file:**
```python
"""Built-in SMB category list used to enumerate a region in grid mode.
Editable per country — this is the completeness dial."""

from __future__ import annotations

DEFAULT_CATEGORIES: list[str] = [
    "restaurant", "cafe", "bar", "bakery", "hairdresser", "barber shop",
    "beauty salon", "nail salon", "plumber", "electrician", "carpenter",
    "painter", "roofer", "cleaning service", "landscaper", "garden center",
    "car repair", "car wash", "auto parts store", "dentist", "physiotherapist",
    "veterinarian", "florist", "butcher", "greengrocer", "clothing store",
    "shoe store", "jeweler", "optician", "pharmacy", "pet store", "bookstore",
    "hardware store", "furniture store", "bike shop", "tailor", "dry cleaner",
    "photographer", "driving school", "real estate agency", "accountant",
    "law firm", "travel agency", "gym", "yoga studio", "tattoo parlor",
]
```

- [ ] **Step 2: Verify import + mypy**

Run: `./.venv/Scripts/python.exe -c "from scraper.categories import DEFAULT_CATEGORIES; print(len(DEFAULT_CATEGORIES))"`
Expected: `46`

### Task 2.4: `config.py` — geocode cache path

**Files:** Modify `src/scraper/config.py`

- [ ] **Step 1: Add the setting** after `SCRAPER_MAX_DELAY_MS` (line 21):
```python
    SCRAPER_GEOCODE_CACHE: str = ".geocode_cache.json"
```

- [ ] **Step 2: Verify**

Run: `./.venv/Scripts/python.exe -c "from scraper.config import settings; print(settings.SCRAPER_GEOCODE_CACHE)"`
Expected: `.geocode_cache.json`

### Task 2.5: Add region/grid fields to `ScrapeParams` (round-trip TDD)

**Files:** Modify `src/scraper/models.py`; Modify `tests/test_models.py`

- [ ] **Step 1: Write the failing model tests** (append to `tests/test_models.py`):
```python
def test_scrape_params_grid_defaults():
    p = ScrapeParams()
    assert p.region is None
    assert p.bbox is None
    assert p.grid_cell_km == 1.2
    assert p.grid_zoom == 16
    assert p.categories == []
    assert p.max_cells == 300


def test_scrape_params_grid_fields_roundtrip():
    p = ScrapeParams(
        region="Lelystad",
        bbox=(52.4, 5.4, 52.6, 5.6),
        grid_cell_km=1.0,
        grid_zoom=15,
        categories=["restaurant", "bakery"],
        max_cells=50,
    )
    restored = ScrapeParams.model_validate(p.model_dump())
    assert restored.region == "Lelystad"
    assert restored.bbox == (52.4, 5.4, 52.6, 5.6)
    assert restored.categories == ["restaurant", "bakery"]
    assert restored.grid_cell_km == 1.0
    assert restored.grid_zoom == 15
    assert restored.max_cells == 50
```

- [ ] **Step 2: Run — expect FAIL** (`extra="forbid"` rejects unknown kwargs)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_models.py -q -k grid`
Expected: FAIL — validation error / attribute missing

- [ ] **Step 3: Add the fields** to `ScrapeParams` after `direct_url` (line 48):
```python
    # Region-first grid mode. When `region` or `bbox` is set, the engine tiles
    # the area into cells and runs one viewport-scoped query per cell × category.
    region: str | None = None
    bbox: tuple[float, float, float, float] | None = None  # min_lat,min_lng,max_lat,max_lng
    grid_cell_km: float = 1.2
    grid_zoom: int = 16
    categories: list[str] = Field(default_factory=list)  # empty → DEFAULT_CATEGORIES
    max_cells: int = 300  # 0 = unlimited (grid-size guard; no checkpoint/resume yet)
```

- [ ] **Step 4: Run — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_models.py -q`
Expected: PASS. (NOTE: `test_every_scrape_params_field_is_referenced_in_engine` in `test_google_maps_pure.py` will now FAIL until Task 2.6 wires the fields — that is expected mid-phase red.)

### Task 2.6: Viewport `_search_url`, `GridTooLargeError`, `_build_grid_queries`, wire `scrape()` (TDD)

**Files:** Modify `src/scraper/google_maps.py`; Modify `tests/test_google_maps_pure.py`

- [ ] **Step 1: Write the failing pure tests** (append to `tests/test_google_maps_pure.py`):
```python
def test_search_url_legacy_no_center_unchanged():
    url = _search_url("restaurants in Lelystad", language="nl", country="NL")
    assert url == "https://www.google.com/maps/search/restaurants+in+Lelystad/?hl=nl&gl=NL"


def test_search_url_with_center_embeds_viewport():
    url = _search_url("restaurant", "en", "NL", center=(52.5, 5.47), zoom=16)
    assert url == "https://www.google.com/maps/search/restaurant/@52.5,5.47,16z?hl=en&gl=NL"


def test_build_grid_queries_bbox_mode_counts():
    from scraper.google_maps import _build_grid_queries

    p = ScrapeParams(
        bbox=(52.0, 5.0, 52.045, 5.073), categories=["restaurant", "bakery"], grid_cell_km=1.0
    )
    plan = _build_grid_queries(p)
    n_cells = len({c for _q, c, _z in plan})
    assert len(plan) == n_cells * 2
    assert all(z == 16 for _q, _c, z in plan)
    assert {q for q, _c, _z in plan} == {"restaurant", "bakery"}


def test_build_grid_queries_defaults_to_default_categories():
    from scraper.categories import DEFAULT_CATEGORIES
    from scraper.google_maps import _build_grid_queries

    p = ScrapeParams(bbox=(52.0, 5.0, 52.01, 5.01), grid_cell_km=1.0)  # ~1 cell
    plan = _build_grid_queries(p)
    assert {q for q, _c, _z in plan} == set(DEFAULT_CATEGORIES)


def test_build_grid_queries_no_region_falls_back_to_text():
    from scraper.google_maps import _build_grid_queries

    p = ScrapeParams(category="restaurants", country="NL", cities=["Lelystad"])
    assert _build_grid_queries(p) == [("restaurants in Lelystad", None, 16)]


def test_build_grid_queries_raises_over_max_cells():
    from scraper.google_maps import GridTooLargeError, _build_grid_queries

    p = ScrapeParams(bbox=(52.0, 5.0, 52.1, 5.1), grid_cell_km=1.0, max_cells=2, categories=["x"])
    with pytest.raises(GridTooLargeError):
        _build_grid_queries(p)
```

- [ ] **Step 2: Run — expect FAIL** (`_build_grid_queries`/`GridTooLargeError` undefined; viewport URL test fails)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_google_maps_pure.py -q -k "search_url or grid_queries"`
Expected: FAIL

- [ ] **Step 3: Add imports** to `google_maps.py`. After `from urllib.parse import ...` add to the stdlib group:
```python
from pathlib import Path
```
After `from .dedup import (...)` block, add to the local-imports group:
```python
from .categories import DEFAULT_CATEGORIES
from .geo import bbox_for_place, grid_centers
```

- [ ] **Step 4: Replace `_search_url`** (currently lines 627-629) with the viewport-aware version:
```python
def _search_url(
    query: str,
    language: str,
    country: str,
    center: tuple[float, float] | None = None,
    zoom: int = 16,
) -> str:
    slug = _SPACE_RE.sub("+", query.strip())
    url = f"https://www.google.com/maps/search/{slug}/"
    if center is not None:
        lat, lng = center
        url += f"@{lat},{lng},{zoom}z"  # explicit viewport — supplies the geography
    return url + f"?hl={language}&gl={country}"
```

- [ ] **Step 5: Add `GridTooLargeError` + `_build_grid_queries`** immediately after `_search_url`:
```python
class GridTooLargeError(ValueError):
    """Raised when a region's grid exceeds max_cells (no checkpoint/resume yet)."""


def _build_grid_queries(
    params: ScrapeParams,
) -> list[tuple[str, tuple[float, float] | None, int]]:
    """Plan the scoped queries.

    Region/bbox mode → one bare-category query per grid cell × category, each
    scoped by a viewport centre. Otherwise → legacy text queries (centre=None).
    Returns a fully-materialised list so an oversized grid fails before any
    browser launch."""
    if params.bbox is not None or params.region is not None:
        if params.bbox is not None:
            bbox = params.bbox
        else:
            assert params.region is not None
            bbox = bbox_for_place(
                params.region, cache_path=Path(settings.SCRAPER_GEOCODE_CACHE)
            )
        cats = params.categories or DEFAULT_CATEGORIES
        grid = list(grid_centers(*bbox, cell_km=params.grid_cell_km))
        logger.info(
            "grid plan: {} cells × {} categories = {} scoped queries",
            len(grid),
            len(cats),
            len(grid) * len(cats),
        )
        if params.max_cells and len(grid) > params.max_cells:
            raise GridTooLargeError(
                f"grid has {len(grid)} cells > max_cells={params.max_cells}; "
                "narrow --region/--bbox or raise --max-cells (0 = unlimited)"
            )
        return [(cat, center, params.grid_zoom) for center in grid for cat in cats]
    return [(query, None, params.grid_zoom) for query in _build_queries(params)]
```

- [ ] **Step 6: Wire `scrape()`**. After the `expanded_direct_url` block (right before `async with async_playwright() as pw:`), add:
```python
    # Build the scoped-query plan BEFORE launching Chromium so a bad region or
    # oversized grid fails in ms (mirrors the direct_url pre-validation above).
    grid_queries: list[tuple[str, tuple[float, float] | None, int]] = []
    if expanded_direct_url is None:
        grid_queries = _build_grid_queries(params)
```
Then in the search-feed loop, change:
```python
            for query in _build_queries(params):
                logger.info("query: {}", query)
                await page.goto(
                    _search_url(query, params.language, params.country),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
```
to:
```python
            for query_text, center, zoom in grid_queries:
                logger.info("query: {!r} @ {}", query_text, center)
                await page.goto(
                    _search_url(query_text, params.language, params.country, center, zoom),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
```
**Leave the rest of the loop (consent, `_collect_place_links`, `peek_external_id` pre-dedup, `_scrape_one_place`, post-dedup, `_passes_filters`, `yield`) unchanged.**

- [ ] **Step 7: Run the pure suite — expect PASS, including the field-reference invariant**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_google_maps_pure.py -q`
Expected: PASS (includes `test_every_scrape_params_field_is_referenced_in_engine`)

- [ ] **Step 8: Full types + suite**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; all tests PASS

### Task 2.7: CLI flags + new defaults (TDD)

**Files:** Modify `src/scraper/cli.py`; Modify `tests/test_cli.py`

- [ ] **Step 1: Write the failing CLI tests** (append to `tests/test_cli.py`):
```python
def test_scrape_region_builds_grid_mode_params(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters(found=5, inserted=5, skipped=0)

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            ["scrape", "--region", "Lelystad", "--dry-run", "--out", str(tmp_path / "o.json")],
        )

    assert result.exit_code == 0, result.stdout
    p = captured[0]
    assert p.region == "Lelystad"
    assert p.categories == []  # empty → engine uses DEFAULT_CATEGORIES
    assert p.max_results_per_area == 120
    assert p.filters.min_reviews is None


def test_scrape_legacy_category_city_defaults(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters()

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape", "--category", "restaurants", "--city", "Lelystad",
                "--dry-run", "--out", str(tmp_path / "o.json"),
            ],
        )

    assert result.exit_code == 0, result.stdout
    p = captured[0]
    assert p.category == "restaurants"  # legacy single-category preserved
    assert p.categories == []
    assert p.region is None
    assert p.max_results_per_area == 120
    assert p.filters.min_reviews is None


def test_scrape_rejects_malformed_bbox():
    with patch("scraper.cli.run_pipeline") as mock_pipeline:
        result = runner.invoke(app, ["scrape", "--bbox", "1,2,3", "--dry-run"])
    assert result.exit_code != 0
    mock_pipeline.assert_not_called()
```

- [ ] **Step 2: Run — expect FAIL** (no `--region`/`--bbox`; old defaults)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q -k "region or legacy_category or malformed"`
Expected: FAIL

- [ ] **Step 3: Add the bbox parser** to `cli.py` (after `_build_sinks_single`):
```python
def _parse_bbox(raw: str | None) -> tuple[float, float, float, float] | None:
    if raw is None:
        return None
    parts = [p.strip() for p in raw.split(",")]
    if len(parts) != 4:
        raise typer.BadParameter(
            "--bbox must be 'min_lat,min_lng,max_lat,max_lng' (4 comma-separated numbers)"
        )
    try:
        return (float(parts[0]), float(parts[1]), float(parts[2]), float(parts[3]))
    except ValueError as exc:
        raise typer.BadParameter(f"--bbox values must be numbers: {raw!r}") from exc
```

- [ ] **Step 4: Update the `scrape` command signature.** Change `category` to repeatable and add grid options; change `max`/`min_reviews` defaults:
```python
    category: Annotated[list[str], typer.Option("--category")] = [],  # noqa: B006
```
```python
    max: Annotated[int, typer.Option("--max")] = 120,
```
```python
    min_reviews: Annotated[int | None, typer.Option("--min-reviews")] = None,
```
Add these new options (place after `area` and before `max`):
```python
    region: Annotated[str | None, typer.Option("--region")] = None,
    bbox: Annotated[str | None, typer.Option("--bbox")] = None,
    grid_cell_km: Annotated[float, typer.Option("--grid-cell-km")] = 1.2,
    grid_zoom: Annotated[int, typer.Option("--grid-zoom")] = 16,
    max_cells: Annotated[int, typer.Option("--max-cells")] = 300,
```

- [ ] **Step 5: Rewrite the `scrape` body.** Replace the `params = ScrapeParams(...)` … through the `counters = asyncio.run(...)` / `typer.echo(...)` block with:
```python
    parsed_bbox = _parse_bbox(bbox)
    grid_mode = bool(region) or parsed_bbox is not None
    params = ScrapeParams(
        category=(category[0] if category else "businesses"),
        categories=list(category) if grid_mode else [],
        country=country,
        cities=list(city),
        areas=list(area),
        max_results_per_area=max,
        language=language,
        with_reviews=with_reviews,
        review_limit=review_limit,
        lead_type=lead_type,  # type: ignore[arg-type]
        region=region,
        bbox=parsed_bbox,
        grid_cell_km=grid_cell_km,
        grid_zoom=grid_zoom,
        max_cells=max_cells,
        filters=ScrapeFilters(
            min_rating=min_rating,
            max_rating=max_rating,
            min_reviews=min_reviews,
            max_reviews=max_reviews,
            web_presence=list(web_presence),  # type: ignore[arg-type]
        ),
    )
    sinks = _build_sinks(dry_run=dry_run, supabase=not no_supabase, out_path=out)
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    try:
        counters = asyncio.run(run_pipeline(params, sinks))
    except ValueError as exc:
        # GridTooLargeError (cap) and the geocode-miss ValueError both surface here.
        raise typer.BadParameter(str(exc)) from exc
    typer.echo(json.dumps(counters.__dict__))
```

- [ ] **Step 6: Run the CLI tests — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q`
Expected: PASS (existing scrape-url tests + 3 new)

- [ ] **Step 7: Full green gate**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; ruff clean; ALL tests PASS

- [ ] **Step 8 (commit — on Stefan's go-ahead):**
```bash
git add scraper/src/scraper/geo.py scraper/src/scraper/categories.py scraper/src/scraper/config.py scraper/src/scraper/models.py scraper/src/scraper/google_maps.py scraper/src/scraper/cli.py scraper/tests/test_geo.py scraper/tests/test_google_maps_pure.py scraper/tests/test_models.py scraper/tests/test_cli.py
git commit -m "feat(scraper): grid tiling × category enumeration for exhaustive area coverage"
```

---

## PHASE 3 — Verification (no new behavior)

### Task 3.1: Adversarial review + manual smoke

- [ ] **Step 1: Full automated gate**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy `Success`; ruff clean; all tests PASS.

- [ ] **Step 2: Adversarial review** — dispatch subagents/Workflow to check the diff against the spec for: (a) `scrape-url` path untouched; (b) legacy `--category --city` unchanged; (c) dedup `seen_ids` still run-wide across the grid; (d) no new mypy errors; (e) `_build_grid_queries` references every `ScrapeParams` field.

- [ ] **Step 3: Manual smoke (Stefan / operator)** — these hit live Google/Nominatim, so they are manual, not CI:
  1. `python -m scraper.cli scrape --category restaurants --city Lelystad --dry-run` (legacy) writes JSON.
  2. `python -m scraper.cli scrape --region "Lelystad" --max-cells 4 --dry-run` (grid, small cap) returns many multiples vs (1), no duplicate `external_id`s.
  3. `python -m scraper.cli scrape-url "<known place URL>" --dry-run` byte-for-byte unchanged.
  4. Spot-check 10 leads: real businesses; `web_presence` correct; <5-review businesses now appear.
  5. One `--no-headless` run to confirm the viewport centres on each cell.

---

## Self-Review (completed during planning)

**Spec coverage:** Phase 0 (mypy gate) ✓; Phase 1 (cap 120 / review floor None / scroll hardening + end-text) ✓; Phase 2 (geo.py, categories.py, viewport URL, `_build_grid_queries`, CLI flags, `--max-cells` guard, geocode cache) ✓; all spec test items mapped to Tasks 2.1-2.7 ✓; explicit OUT items (Phase 3 robustness, CMS form, DB migration) not scheduled ✓.

**Placeholder scan:** none — every code step shows full code.

**Type consistency:** `_build_grid_queries -> list[tuple[str, tuple[float,float]|None, int]]` consistent across model, engine, and tests; `bbox` order `(min_lat,min_lng,max_lat,max_lng)` consistent in `geo`, `models`, `_build_grid_queries`, and CLI `_parse_bbox`; `GridTooLargeError` defined in `google_maps.py` and caught (as `ValueError`) in `cli.py`.
