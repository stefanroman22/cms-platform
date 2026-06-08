# Implementation Prompt — RT Scraper Lead-Coverage Overhaul

> Paste everything below into Claude Code (run from the `scraper/` repo root). It is written to be executed directly by a coding agent. It assumes the `superpowers` plugin is installed.

---

## 0. Operating instructions (read first)

**Use the `superpowers` skill for this entire task.** Do not start writing implementation code immediately.

1. If `superpowers` is not installed, install it: `/plugin install superpowers@claude-plugins-official`.
2. **Begin with `/brainstorming`** to explore intent, confirm the design, and surface trade-offs/edge cases. Ask me questions one at a time; prefer multiple-choice. Do not write production code during this phase.
3. Then use the **writing-plans** skill to produce a written implementation plan with explicit phases and checkpoints.
4. Then use **`/execute-plan`** to implement, following superpowers' **test-driven development** discipline (write the failing test first, then the code) and using **subagents to verify** each phase before moving on.
5. Commit in small, reviewable increments at the phase boundaries defined in §8. Keep `mypy` and the existing test suite green at every commit.

Work strictly within this repo. Do not refactor unrelated code. Preserve all existing behaviour that this prompt does not explicitly change (especially the `scrape-url` single-business path, which already works perfectly).

---

## 1. What this project is

`rt-scraper` is a self-contained Python package that harvests business leads from **Google Maps** for an outbound pipeline (target: businesses **without a website**, to pitch them one). It runs as a long-lived process on a Hetzner VM via a systemd timer. **No paid APIs** (no Google Places, no SerpAPI) and no photo downloads — public DOM data and image URLs only.

**Stack**
- Python 3.11+, `src/` layout, package import root `scraper`.
- **Playwright** (async, Chromium) for scraping.
- **Typer** CLI (entry point `scraper`), **Pydantic v2** models, **pydantic-settings** config, **loguru** logging, **tenacity** retries.
- **pytest** for tests, **mypy** for typing (must stay clean).
- Sinks: JSON (dry-run) and **Supabase** (upsert on `external_id`, idempotent).

**File map (source of truth — read these before changing anything)**
- `src/scraper/models.py` — Pydantic models: `ScrapeParams`, `ScrapeFilters`, `Lead`.
- `src/scraper/google_maps.py` — Playwright engine: `scrape()` (async generator), `_build_queries()`, `_search_url()`, `_collect_place_links()`, `_scrape_one_place()`, `_passes_filters()`, `_new_context()` (has a proxy extension hook), `_with_hl()`.
- `src/scraper/dedup.py` — pure helpers: `peek_external_id()`, `external_id_from_url()`, `parse_latlng_from_url()`, `normalize_name()`, `classify_web_presence()`.
- `src/scraper/selectors.py` — **all** DOM selectors live here (e.g. `RESULTS_FEED = 'div[role="feed"]'`, `RESULTS_ITEM_LINK = "a.hfpxzc"`, `RESULTS_END_MARKER = "p.HlvSq, span.HlvSq"`).
- `src/scraper/urls.py` — Google Maps URL validation + short-link expansion.
- `src/scraper/cli.py` — Typer commands: `scrape`, `scrape-url`, `run-pending`.
- `src/scraper/config.py` — `Settings` (headless flag, UA, `SCRAPER_MIN_DELAY_MS`/`MAX`).
- `src/scraper/pipeline.py` — `run_pipeline()` + `Counters`.
- `src/scraper/sinks/` — `base.py`, `json_sink.py`, `supabase_sink.py`.
- `tests/` — `test_cli.py`, `test_dedup.py`, `test_google_maps_pure.py`, `test_models.py`, `test_pipeline.py`, `test_sinks_json.py`, `test_urls.py`.

---

## 2. The problem to solve

When scraping a **whole city or country**, the scraper finds far fewer leads than exist. Single-business lookups (`scrape-url`) and tight `category + city` searches work fine; broad area searches do not.

**Root causes (confirmed):**

1. **Google Maps caps any single search at ~120 results**, then shows "You've reached the end of the list." This is a Google-side limit. One query can never enumerate a city/country. (See references in §10.)
2. **`ScrapeParams.max_results_per_area = 20`** (and CLI `--max` default 20) throttles every query to 20 — far below even the 120 wall.
3. **`_search_url()` sets no map viewport.** It builds `/maps/search/<query>/?hl=&gl=` with no `@lat,lng,zoom`, so Google chooses the viewport from the text. `businesses in NL` → a national viewport → a thin, capped feed.
4. **The generic keyword `businesses` is a weak enumerator.** Google Maps has no real "all businesses" query; reliable enumeration comes from iterating concrete categories.
5. **`ScrapeFilters.min_reviews = 5` is ON by default** and silently drops every business with fewer than 5 reviews — i.e. exactly the tiny, new, no-website businesses we want most.
6. **`_collect_place_links()` can stop early** — it scrolls by full `scrollHeight` (can outrun lazy loading) and gives up after only 3 stable rounds; the end-marker selector is a fragile obfuscated class.

---

## 3. Goal & acceptance criteria

**Goal:** the operator types only a **place name** (city or region) — no category — and the scraper returns **as many correct leads as possible**, exhaustively covering the area. Quality and completeness over speed.

**Acceptance criteria (Definition of Done):**
- A new region-first command runs end to end, e.g.:
  `python -m scraper.cli scrape --region "Lelystad" --dry-run` (no `--category`) and produces **many multiples** of the previous result count for the same area.
- No category input is required; categories are generated internally from a built-in list.
- Results are deduplicated run-wide (no business appears twice) using the existing `external_id` logic.
- The default no-website target segment (businesses with 0–4 reviews) is **no longer filtered out** by default.
- `scrape-url` (single business) behaviour is **unchanged**.
- All existing + new tests pass; `mypy` is clean.
- The `--category … --city …` legacy mode still works (backward compatible).

---

## 4. Design to implement

Replace "one text query per area" with **geographic grid tiling × category enumeration**, each query scoped by an explicit map viewport so it stays under the 120 cap; union and dedupe the results.

```
"Amsterdam"
   │  Nominatim (free OSM geocoder) → bounding box
   ▼
bbox = (min_lat, min_lng, max_lat, max_lng)
   │  tile into ~1–1.5 km cells
   ▼
grid = [(lat₁,lng₁), …]                          # N cells
   │  for each cell × each category (M categories)
   ▼
GET /maps/search/<category>/@lat,lng,16z          # N×M scoped queries, each ≤120
   │
   ▼  collect links → _scrape_one_place → Lead
   ▼  run-wide dedup by external_id  (ALREADY EXISTS)
   ▼  filters → sinks
```

Key insight: the **viewport (`@lat,lng,zoom`) supplies the geography**, so the text query can be just the bare category. The existing per-place extraction, retry, dedup, filter, and sink machinery is reused unchanged.

---

## 5. Detailed work items (file-by-file)

> Snippets below are reference implementations — adapt to match the repo's style and keep everything typed for mypy. Write tests first (§6).

### 5.1 `src/scraper/models.py` — extend `ScrapeParams`, fix `ScrapeFilters`

Add region-first fields to `ScrapeParams`:
```python
region: str | None = None                                   # e.g. "Amsterdam"
bbox: tuple[float, float, float, float] | None = None       # min_lat, min_lng, max_lat, max_lng
grid_cell_km: float = 1.2                                    # cell size; smaller = more thorough
grid_zoom: int = 16                                          # viewport zoom per cell
categories: list[str] = Field(default_factory=list)         # empty → DEFAULT_CATEGORIES
```
Change the per-query cap default:
```python
max_results_per_area: int = 120        # was 20 — let each scoped cell fill to Google's ceiling
```
Fix the filter that hides target leads:
```python
class ScrapeFilters(BaseModel):
    ...
    min_reviews: int | None = None     # was 5 — stop deleting micro-businesses without websites
```
Keep `model_config = ConfigDict(extra="forbid")`. These are additive; existing callers still validate.

### 5.2 `src/scraper/geo.py` — NEW pure-ish module (grid + geocoding)

```python
"""Geo helpers: bounding-box geocoding (Nominatim) + grid tiling.
Grid math is pure and unit-tested; bbox_for_place does cached HTTP IO."""
from __future__ import annotations
import json, math, time, urllib.parse, urllib.request
from collections.abc import Iterator

def grid_centers(min_lat: float, min_lng: float, max_lat: float, max_lng: float,
                 cell_km: float = 1.2) -> Iterator[tuple[float, float]]:
    """Yield (lat, lng) cell centres covering the bbox."""
    dlat = cell_km / 111.0
    lat = min_lat + dlat / 2
    while lat < max_lat:
        dlng = cell_km / (111.0 * math.cos(math.radians(lat)))
        lng = min_lng + dlng / 2
        while lng < max_lng:
            yield round(lat, 6), round(lng, 6)
            lng += dlng
        lat += dlat

_NOMINATIM = "https://nominatim.openstreetmap.org/search"
_GEO_CACHE: dict[str, tuple[float, float, float, float]] = {}   # persist to disk for long runs

def bbox_for_place(name: str) -> tuple[float, float, float, float]:
    """Return (min_lat, min_lng, max_lat, max_lng) for a place name.
    Honours Nominatim policy: descriptive User-Agent, ≤1 req/s, cache results."""
    if name in _GEO_CACHE:
        return _GEO_CACHE[name]
    q = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
    req = urllib.request.Request(
        f"{_NOMINATIM}?{q}",
        headers={"User-Agent": "rt-scraper/1.0 (ops@romantech.example)"},
    )
    time.sleep(1.0)  # rate-limit guard
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    if not data:
        raise ValueError(f"no geocoding result for {name!r}")
    s, n, w, e = (float(x) for x in data[0]["boundingbox"])  # [south, north, west, east]
    box = (s, w, n, e)
    _GEO_CACHE[name] = box
    return box
```
Notes: cache to a small on-disk JSON so repeated runs don't re-hit Nominatim. Keep `grid_centers` IO-free so it lives in the pure-test suite.

### 5.3 `src/scraper/categories.py` — NEW built-in category list

```python
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
This is the completeness dial — keep it editable and easy to extend per country.

### 5.4 `src/scraper/google_maps.py` — viewport URL + grid query loop + sturdier scroll

**(a) Viewport-aware search URL** (replace `_search_url`):
```python
def _search_url(query: str, language: str, country: str,
                center: tuple[float, float] | None = None, zoom: int = 16) -> str:
    slug = _SPACE_RE.sub("+", query.strip())
    url = f"https://www.google.com/maps/search/{slug}/"
    if center is not None:
        lat, lng = center
        url += f"@{lat},{lng},{zoom}z"        # explicit viewport — the key change
    return url + f"?hl={language}&gl={country}"
```

**(b) Grid query generator** (new; keep `_build_queries` as the legacy fallback):
```python
from .geo import bbox_for_place, grid_centers
from .categories import DEFAULT_CATEGORIES

def _build_grid_queries(params: ScrapeParams):
    """Yield (query_text, center, zoom). Region/bbox → grid×categories; else legacy text mode."""
    if params.bbox or params.region:
        bbox = params.bbox or bbox_for_place(params.region)  # type: ignore[arg-type]
        cats = params.categories or DEFAULT_CATEGORIES
        for center in grid_centers(*bbox, cell_km=params.grid_cell_km):
            for cat in cats:
                yield cat, center, params.grid_zoom
    else:
        for q in _build_queries(params):
            yield q, None, params.grid_zoom
```

**(c) Swap the search loop in `scrape()`** to iterate `_build_grid_queries(params)` instead of `_build_queries(params)`. For each item build the URL with `_search_url(query_text, params.language, params.country, center, zoom)`. **Everything inside the loop stays the same**: `_collect_place_links`, the `peek_external_id` pre-visit dedup, `_scrape_one_place`, the post-visit `seen_ids` check, `_passes_filters`, `yield lead`. The run-wide `seen_ids` set already dedupes across cells and categories — keep it.

**(d) Harden `_collect_place_links()`:** scroll in smaller steps (≈80% of the feed's client height, not full `scrollHeight`), wait for the link count to actually grow between scrolls, raise the stable-round threshold (e.g. 5), and detect end-of-list by **visible text** in addition to the fragile class. Add to `selectors.py`:
```python
# End-of-list sentinel text (class names drift; match text too). Lowercased contains-checks.
RESULTS_END_TEXTS: tuple[str, ...] = (
    "you've reached the end of the list",
    "je hebt het einde van de lijst bereikt",   # nl
    "ende der liste",                            # de
)
```
Implement a small `_feed_has_end_text(page)` helper that reads the feed's inner text and checks for any sentinel (case-insensitive).

### 5.5 `src/scraper/cli.py` — new flags (backward compatible)

Add to the `scrape` command, mapping into `ScrapeParams`:
- `--region TEXT` (place name → grid mode)
- `--bbox "min_lat,min_lng,max_lat,max_lng"` (explicit bbox → grid mode; parse to a 4-tuple)
- `--grid-cell-km FLOAT` (default 1.2)
- `--grid-zoom INT` (default 16)
- keep `--category` **repeatable** to optionally override `DEFAULT_CATEGORIES`; when `--region` is given and no `--category`, use the built-in list.
- Change `--max` default to **120**.
- Change `--min-reviews` default to **None** (no floor) to match the model.

Precedence: if `--region`/`--bbox` is present, run grid mode; else fall back to the existing `--category/--city/--area` text mode. Do not break `run-pending` (it deserialises `ScrapeParams` from Supabase — the new optional fields are additive).

### 5.6 Long-run robustness (Phase 3 — see §8)

- **Checkpoint/resume:** persist completed `(cell, category)` pairs (e.g. in `scrape_jobs.params` or a child table) so a multi-thousand-query region run resumes after a crash/IP block instead of restarting.
- **Cell-split on saturation:** if a `(cell, category)` returns ~120 results, subdivide that cell into 4 and re-run it, so dense city centres don't silently lose the overflow.
- **Proxy rotation:** wire the existing `_new_context()` proxy hook (add a `proxy={"server": ...}` kwarg) behind a config flag for when Google challenges the Hetzner IP.

---

## 6. Tests (write these FIRST — TDD)

Extend the existing pure-logic suites; mirror the style in `tests/test_dedup.py` and `tests/test_google_maps_pure.py`.

- `tests/test_geo.py` (new):
  - `grid_centers` returns the expected count for a known bbox (e.g. a ~5×5 km box at 1.0 km → ~25 cells; at 1.2 km → ~16 cells), centres lie inside the bbox, and longitude spacing widens with latitude.
  - `bbox_for_place` parses Nominatim's `[south, north, west, east]` into `(min_lat, min_lng, max_lat, max_lng)` correctly — **mock the HTTP call**, assert caching avoids a second request, and assert the empty-result path raises.
- `test_google_maps_pure.py` (extend):
  - `_search_url` with `center=None` matches the legacy URL; with a center it embeds `/@lat,lng,16z` before the `?` query.
  - `_build_grid_queries`: region/bbox mode yields `len(categories) × len(grid)` tuples; no-region mode falls back to text queries; explicit `categories` override the default list.
- `test_models.py` (extend):
  - `ScrapeFilters().min_reviews is None` (regression guard against the old default of 5).
  - `ScrapeParams().max_results_per_area == 120`.
  - new fields validate and round-trip through `model_validate`/`model_dump` (the Supabase path depends on this).
- `test_cli.py` (extend): `--region` produces a grid-mode `ScrapeParams`; `--max`/`--min-reviews` defaults are 120/None; legacy `--category --city` still works.

Keep Playwright out of unit tests (the pure helpers are deliberately IO-free — preserve that boundary).

---

## 7. Edge cases & constraints

- **Nominatim usage policy:** descriptive `User-Agent`, **max 1 request/second**, and **cache** results. Never hammer it inside the grid loop — geocode once per region, then tile locally.
- **Dedup across cells is mandatory** — adjacent cells and overlapping categories will surface the same business repeatedly. Rely on the existing `external_id` (Google `!1s` feature id) and `peek_external_id` pre-visit skip; do not weaken them.
- **Do not add paid APIs.** Paying for the official Places API would **not** remove the need for the grid (its Text/Nearby Search caps at ~60 results per query) and breaks the no-paid-API rule.
- **Keep selectors centralised** in `selectors.py`; engine logic must not hardcode DOM strings.
- **`scrape-url` path is sacred** — it bypasses search/feed/filters and already works; don't touch its behaviour.
- **`Lead` schema changes must be additive** (Supabase upsert depends on the shape). This work needs no new `Lead` fields.
- **Politeness:** preserve `_polite_delay()`; for very long runs add a longer jittered pause every N place-pages.
- **Determinism in tests:** mock network; don't rely on live Google/Nominatim in CI.

---

## 8. Phased rollout & commit plan

**Phase 1 — quick wins (independent value, ship first).**
`max_results_per_area` → 120; `min_reviews` default → None; harden `_collect_place_links()` + end-text sentinels. Update `test_models.py`/`test_cli.py`. Commit: `feat(scraper): raise per-query cap, drop default review floor, sturdier feed scroll`.

**Phase 2 — region-first grid (the core fix).**
Add `geo.py`, `categories.py`, viewport `_search_url`, `_build_grid_queries`, CLI `--region/--bbox/--grid-*`, and tests. Wire the `scrape()` loop. Commit: `feat(scraper): grid tiling × category enumeration for exhaustive area coverage`.

**Phase 3 — long-run robustness.**
Checkpoint/resume, cell-split on saturation, proxy hook. Commit per item.

**Phase 4 — (optional, later) cross-source.**
Add an OSM/Overpass engine emitting the same `Lead` shape to fill gaps and double-confirm "no website"; reconcile on name+geo. Separate task.

Run `pytest` and `mypy` before every commit. Use a subagent to review each phase's diff against this spec before moving on.

---

## 9. Manual verification before you call it done

1. `python -m scraper.cli scrape --category restaurants --city Lelystad --dry-run` (legacy mode) still works and writes JSON.
2. `python -m scraper.cli scrape --region "Lelystad" --dry-run` (grid mode, **no category**) returns **many multiples** more leads than (1), with no duplicate `external_id`s in the output.
3. `python -m scraper.cli scrape-url "<a known place URL>" --dry-run` is byte-for-byte unchanged from before.
4. Spot-check 10 random leads: each is a real business, web_presence is correctly `none`/`social_only`, and businesses with <5 reviews now appear.
5. Watch one run with `--no-headless` to confirm the viewport actually centres on each cell.

---

## 10. References (background; cite if you document decisions)

- Google's ~120-results-per-search cap and the coords+zoom+multi-query workaround — omkarcloud maintainer: https://github.com/omkarcloud/google-maps-scraper/discussions/132
- Grid mode in a popular Maps scraper (`-grid-bbox`, `-grid-cell` km, `-zoom`): https://github.com/gosom/google-maps-scraper
- "Scraping more than 120 results from Google Maps": https://rayobyte.com/university/courses/google-maps/more-than-120-results/
- Google Places API limits (why paying doesn't remove the grid need): https://blog.apify.com/google-places-api-limits/
- Nominatim API + usage policy (free geocoding for bounding boxes): https://nominatim.org/release-docs/latest/api/Overview/
- superpowers methodology (use it for this task): https://github.com/obra/superpowers

---

### One-line kickoff (what to type after pasting this)

> "Use superpowers. Start with `/brainstorming` on this spec, then write the plan, then `/execute-plan` with TDD. Begin Phase 1 only after I approve the plan."
