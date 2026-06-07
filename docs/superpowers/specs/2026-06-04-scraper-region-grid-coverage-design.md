# RT Scraper — Region-First Grid Coverage (design)

**Date:** 2026-06-04
**Component:** `scraper/` (rt-scraper Python package)
**Status:** approved (brainstorming) → ready for plan

## Problem

Broad-area scrapes (a whole city/country) return far fewer leads than exist.
Single-business (`scrape-url`) and tight `category + city` searches work; broad
searches do not. Confirmed root causes:

1. Google Maps caps any single search at ~120 results ("You've reached the end
   of the list"). One query can't enumerate a city.
2. `ScrapeParams.max_results_per_area = 20` throttles every query below even the
   120 wall.
3. `_search_url()` sets no map viewport, so Google picks a wide viewport from the
   text → thin, capped feed.
4. The generic keyword `businesses` is a weak enumerator.
5. `ScrapeFilters.min_reviews = 5` is ON by default, silently dropping the exact
   micro-businesses (0–4 reviews) we want to pitch.
6. `_collect_place_links()` can stop early (scrolls by full `scrollHeight`, gives
   up after 3 stable rounds, end-marker is a fragile obfuscated class).

## Goal

The operator types only a **place name** (no category) and the scraper returns as
many correct leads as possible, exhaustively covering the area. Completeness over
speed. `scrape-url` and legacy `--category --city` must keep working unchanged.

## Approach (chosen)

Replace "one text query per area" with **geographic grid tiling × category
enumeration**, each query scoped by an explicit `@lat,lng,zoom` viewport so it
stays under the 120 cap; union and dedupe by the existing `external_id` logic.

```
"Lelystad"  ──Nominatim──▶  bbox (min_lat,min_lng,max_lat,max_lng)
            ──tile ~1.2km──▶  grid = [(lat,lng), …]   (N cells)
   for each cell × each category (M):
       GET /maps/search/<category>/@lat,lng,16z        (N×M scoped queries, each ≤120)
   collect links → _scrape_one_place → Lead → run-wide dedup → filters → sinks
```

The viewport supplies the geography, so the text query is the bare category. The
existing per-place extraction, retry, dedup, filter, and sink machinery is reused
unchanged. **Rejected alternatives:** a single text query (can't beat the 120
cap); the paid Places API (caps ~60/query *and* breaks the no-paid-API rule).

## Scope

This session ships **Phase 0 + Phase 1 + Phase 2**. Phase 3 (checkpoint/resume,
cell-split on saturation, proxy rotation) and Phase 4 (cross-source OSM) are
deferred to their own tasks.

### Phase 0 — green the mypy baseline (prerequisite)

The committed scraper is already mypy-red (9 errors); CI (`mypy src`) is failing
on pre-existing code, unrelated to this feature. The operator authorized fixing
these so the "mypy clean" gate is real.

- `[tool.mypy]` in `pyproject.toml`: add `plugins = ["pydantic.mypy"]` — resolves
  the `models.py:25` `Field(default_factory=…)` Literal inference error and
  hardens all future pydantic typing.
- `cli.py` `run_pending()`: type-narrow the Supabase row access (`job["params"]`,
  `job["id"]`) so the JSON union is indexable / assignable to `str | None`.
- DoD: `mypy src` reports **0 errors**; all 87 existing tests still pass.

### Phase 1 — quick wins

- `models.py`: `ScrapeFilters.min_reviews: int | None = None` (was `5`);
  `ScrapeParams.max_results_per_area: int = 120` (was `20`).
- `selectors.py`: add `RESULTS_END_TEXTS: tuple[str, ...]` (en/nl/de sentinels).
- `google_maps.py`:
  - new pure helper `_text_has_end_sentinel(text: str) -> bool` (case-insensitive
    contains-check against `RESULTS_END_TEXTS`) — **unit-tested**.
  - new `async _feed_has_end_text(page) -> bool` reading the feed inner_text and
    delegating to `_text_has_end_sentinel`.
  - harden `_collect_place_links()`: scroll by ~80% of the feed's `clientHeight`
    (not full `scrollHeight`); raise stable-round threshold 3 → 5; break on
    end-marker class **or** `_feed_has_end_text`.
- Tests: update `test_models.py` default assertions to 120 / None (these encode
  the new requirement); add `_text_has_end_sentinel` unit tests. The scroll loop
  itself stays Playwright-driven (verified manually), preserving the IO-free unit
  boundary. (`test_google_maps_pure.py:161,169` already pre-override
  `min_reviews=None`, so they survive.)

### Phase 2 — region-first grid

**`models.py` — additive `ScrapeParams` fields** (stored as JSON in
`scrape_jobs.params`; no DB migration needed):

```python
region: str | None = None
bbox: tuple[float, float, float, float] | None = None   # min_lat,min_lng,max_lat,max_lng
grid_cell_km: float = 1.2
grid_zoom: int = 16
categories: list[str] = Field(default_factory=list)     # empty → DEFAULT_CATEGORIES
max_cells: int = 300                                     # 0 = unlimited (grid guard)
```

`category: str = "businesses"` stays for legacy mode.

**`geo.py` (new):**
- `grid_centers(min_lat, min_lng, max_lat, max_lng, cell_km=1.2) -> Iterator[tuple[float,float]]`
  — pure; longitude spacing widens with latitude via `cos(radians(lat))`.
- `bbox_for_place(name, *, cache_path: Path | None = None) -> tuple[float,float,float,float]`
  — one cached Nominatim call per run; descriptive User-Agent; 1s rate guard;
  in-memory dict cache + optional write-through JSON disk cache; parses
  `boundingbox` `[south, north, west, east]` → `(min_lat,min_lng,max_lat,max_lng)`;
  raises `ValueError` on empty result. The 1s `time.sleep` is patchable in tests.

**`categories.py` (new):** `DEFAULT_CATEGORIES: list[str]` (47 SMB categories).

**`google_maps.py`:**
- `_search_url(query, language, country, center=None, zoom=16)` — appends
  `@lat,lng,{zoom}z` before `?` only when `center` is given; `center=None`
  reproduces the legacy URL byte-for-byte.
- `_build_grid_queries(params) -> list[tuple[str, tuple[float,float]|None, int]]`
  (returns a fully-materialized list so the guard can fail fast before any
  browser launch):
  - region/bbox mode: resolve bbox (`params.bbox` or `bbox_for_place(params.region,
    cache_path=…)`); `cats = params.categories or DEFAULT_CATEGORIES`;
    materialize `grid = list(grid_centers(*bbox, cell_km=params.grid_cell_km))`;
    log `N cells × M cats = N×M queries`; if `params.max_cells` and
    `len(grid) > params.max_cells` → raise `GridTooLargeError`; else return
    `[(cat, center, params.grid_zoom) for center in grid for cat in cats]`.
  - else (no region/bbox): legacy fallback returning
    `[(query, None, params.grid_zoom) for query in _build_queries(params)]`.
  - References every new field by name (satisfies
    `test_every_scrape_params_field_is_referenced_in_engine`).
- `scrape()`: build the plan **before** launching Chromium
  (`grid_queries = _build_grid_queries(params)`), mirroring the existing
  pre-browser `expand_if_short` fail-fast. The search-feed loop iterates
  `grid_queries`, building each URL with the viewport. **The inner loop
  (collect → peek-dedup → scrape_one → post-dedup → filter → yield) is
  untouched.** Run-wide `seen_ids` already dedupes across cells/categories.
- `GridTooLargeError(ValueError)` — defined in `google_maps.py` for clean CLI
  messaging.

**`config.py`:** add `SCRAPER_GEOCODE_CACHE: str = ".geocode_cache.json"`.

**`cli.py` — `scrape` command (backward compatible):**
- new: `--region`, `--bbox "min_lat,min_lng,max_lat,max_lng"` (parsed to a
  4-float tuple, `BadParameter` on malformed), `--grid-cell-km` (1.2),
  `--grid-zoom` (16), `--max-cells` (300).
- `--category` becomes **repeatable** (`list[str]`, default `[]`). Grid mode
  (`--region`/`--bbox` present) → fills `categories` (empty ⇒ DEFAULT_CATEGORIES);
  legacy mode → `category = category[0] if category else "businesses"`, preserving
  today's behavior byte-for-byte.
- `--max` default 20 → 120; `--min-reviews` default 5 → None.
- Wrap `asyncio.run(run_pipeline(...))` in `try/except (GridTooLargeError,
  ValueError)` → `typer.BadParameter` for clean failure on oversized grid or
  geocode miss (mirrors `scrape-url`'s `InvalidMapsURLError` handling).
- `run-pending` untouched (new fields are additive JSON).

**Tests:**
- `test_geo.py` (new): grid count for a known bbox (~5×5 km @ 1.0 km ≈ 25 cells;
  @ 1.2 km ≈ 16); centres inside bbox; lng spacing widens with latitude;
  `bbox_for_place` parses `[s,n,w,e]` correctly with **mocked** `urlopen` +
  patched `time.sleep`; second call hits cache (no 2nd request); empty result
  raises.
- `test_google_maps_pure.py` (extend): `_search_url` legacy vs viewport;
  `_build_grid_queries` yields `len(cats) × len(grid)` in bbox mode, falls back to
  text queries with no region, honors explicit `categories`, and raises
  `GridTooLargeError` past `max_cells`.
- `test_models.py` (extend): new fields validate + round-trip through
  `model_validate`/`model_dump`; `max_cells == 300` default.
- `test_cli.py` (extend): `--region` produces grid-mode params; `--max`/
  `--min-reviews` defaults are 120/None; legacy `--category --city` still works;
  malformed `--bbox` → non-zero exit.

## Decisions beyond the literal spec

1. **Grid guard:** `--max-cells` (default 300), capped on **cells** (not
   cells×categories) so category breadth never trips it. `0` = unlimited.
   Estimate logged before scraping; over-cap raises `GridTooLargeError` →
   `BadParameter`.
2. **`--category` mapping:** repeatable; grid→`categories`, legacy→first-or-
   "businesses". Both model fields (`category`, `categories`) coexist.
3. **Geocode cache:** in-memory dict + write-through JSON at
   `settings.SCRAPER_GEOCODE_CACHE`. Cheap insurance for Nominatim's policy
   (we geocode once per run regardless).

## Explicitly OUT of this session

- Phase 3: checkpoint/resume, cell-split on saturation, proxy rotation.
- The "longer jittered pause every N place-pages" long-run politeness tweak.
- CMS frontend form fields for region mode — **grid mode is CLI-only for now.**
- Any Supabase migration (new `ScrapeParams` fields are additive JSON).

## Constraints (carried from the spec)

- No paid APIs; no photo downloads.
- Nominatim: descriptive UA, ≤1 req/s, cache; geocode once per region then tile
  locally.
- Dedup across cells is mandatory (existing `external_id` + `peek_external_id`).
- Selectors stay centralised in `selectors.py`.
- `scrape-url` path is sacred — untouched.
- `Lead` schema changes are additive only (none needed here).
- Tests mock all network; no live Google/Nominatim in CI.

## Definition of Done

- `mypy src` → 0 errors; `ruff check .` clean; full pytest green (existing + new).
- `scrape --region "Lelystad" --dry-run` (no category) returns many multiples of
  legacy `--category restaurants --city Lelystad --dry-run`, no duplicate
  `external_id`s.
- `scrape-url` output byte-for-byte unchanged.
- Oversized grid (e.g. a province) aborts with a clear message before scraping.
