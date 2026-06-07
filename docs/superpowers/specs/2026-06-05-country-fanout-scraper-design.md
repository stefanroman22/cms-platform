# RT Scraper — Country → Cities Fan-out (design)

**Date:** 2026-06-05
**Component:** `scraper/` (rt-scraper Python package)
**Status:** approved (brainstorming) → ready for plan
**Builds on:** the region-first grid (`2026-06-04-scraper-region-grid-coverage-design.md`)

## Problem & goal

A single nationwide query ("plumbers in NL") hits Google's ~120-cap and clusters
geographically — it does not exhaust a country. The grid exhausts a *place*, but
gridding a whole country at once is ~40k cells (trips the guard) and one giant
job. **Goal:** type a country and exhaustively cover **every city, small and big**,
by fanning out into one grid job per administrative unit, drained by the existing
job queue. Extensible to new countries by dropping in a data file.

## Key research findings (drive the design)

- **NL = 342 municipalities (gemeenten).** The 2,501 *woonplaatsen* (villages/towns)
  **legally partition each municipality with zero gaps**, so gridding a
  municipality's bbox sweeps every village inside it. **Fan out at the municipality
  level (342 jobs) = "all cities, small and big"** — no need to enumerate villages.
- **Existing bug:** `max_cells=300` (~432 km² at 1.2 km) **silently rejects the
  largest rural/coastal municipalities** (e.g. Súdwest-Fryslân ≈ 1,190 cells →
  `GridTooLargeError` → scraped zero times). Must auto-scale the guard for fan-out.
- **Volume reality:** full 46 categories × 1.2 km × 342 munis ≈ **2M queries ≈
  years** — infeasible. "Fully reached" is redefined as **bounded-complete**: every
  municipality covered once across a **curated ~20-category** set, drained by the
  queue over weeks. Curated set ≈ 85% fewer queries; est. 30k–75k no-website leads.
- **Data source (validated):** PDOK CBS Gebiedsindelingen WFS returns all **342**
  gemeente polygons as GeoJSON in WGS84 (CC0, redistributable). One HTTP call;
  properties `statnaam`/`statcode`; compute bbox from coords. No runtime geocoding.

## Scope — Tier A (fan-out MVP)

Ships: region registry + offline seed tool + curated category preset + a
`scrape-country` enqueue command + the guard auto-scale fix.

### 1. Region registry — `src/scraper/regions/`

- `nl.jsonl` — one JSON object per line per municipality:
  ```json
  {"name": "Groningen", "country_code": "NL", "code": "GM0014",
   "bbox": [53.1062, 6.4627, 53.3128, 6.7725], "centroid": [53.21, 6.62],
   "population": 238147, "source": "pdok-cbs-2025"}
  ```
  `bbox` order is `[min_lat, min_lng, max_lat, max_lng]` — matches `grid_centers`
  and `ScrapeParams.bbox` exactly, so an entry feeds the grid with no glue.
  `population` is optional (best-effort enrichment; may be `null`).
- `__init__.py` — `RegionEntry` (pydantic model) + `load_country(cc: str) ->
  list[RegionEntry]` (reads `<cc-lower>.jsonl` via `Path(__file__).parent`, raises
  `ValueError` for an unknown/missing country) + `list_countries() -> list[str]`.
- Packaging: add `[tool.setuptools.package-data]` `"scraper.regions" = ["*.jsonl"]`
  to `pyproject.toml` so the data ships in non-editable installs.

### 2. Seed tool — `tools/build_regions.py` (offline, one-time; not in runtime)

Pure-stdlib (`urllib`, `json`) dev script that regenerates `regions/nl.jsonl`:
1. GET `https://service.pdok.nl/cbs/gebiedsindelingen/2025/wfs/v1_0?request=GetFeature
   &service=WFS&version=2.0.0&typeName=gebiedsindelingen:gemeente_gegeneraliseerd
   &outputFormat=application/json&srsName=EPSG:4326` (validated: 342 features).
2. Per feature: `name=statnaam`, `code=statcode`; compute bbox by walking the
   geometry coords (GeoJSON `[lon,lat]`) → `(min_lat=min(lat), min_lng=min(lon),
   max_lat=max(lat), max_lng=max(lon))`; centroid = bbox midpoint.
3. Best-effort `population` enrichment via Wikidata SPARQL (instance-of Dutch
   municipality → P1082), joined on name. On any failure → `population=null`
   (non-blocking; ordering just falls back).
4. Write `src/scraper/regions/nl.jsonl` sorted by `population` desc (nulls last).
   Assert exactly 342 lines before writing.

Run once during implementation; commit the generated `nl.jsonl`. Re-run only when
CBS boundaries change (stable since 2023).

### 3. Curated category preset — `categories.py`

Add `CURATED_CATEGORIES: list[str]` — a strict subset of `DEFAULT_CATEGORIES`
(~24 high-value independent SMB categories: trades, food, personal services).
**Drops** website-saturated/regulated/chain categories (garden center, auto parts,
dentist, physiotherapist, veterinarian, clothing/shoe store, jeweler, optician,
pharmacy, pet store, bookstore, hardware/furniture store, real estate, accountant,
law firm, travel agency, gym, yoga studio). A test asserts subset membership.

### 4. `scrape-country` CLI command — `cli.py`

```
scrape-country NL [--deep] [--limit N] [--dry-run] [--max-cells-cap N]
```
- Loads `load_country("NL")`.
- For each municipality (population-first order from the file): build a grid
  `ScrapeParams(country="NL", region=<name>, bbox=<entry.bbox>,
  categories=CURATED_CATEGORIES (or DEFAULT_CATEGORIES if --deep),
  grid_cell_km=1.2, grid_zoom=16, max_cells=<auto>)`.
- **Guard auto-scale:** compute the municipality's grid cell count via
  `len(list(grid_centers(*bbox, cell_km=1.2)))` and set `max_cells` to that count,
  so every enqueued municipality runs instead of raising `GridTooLargeError`.
  `--max-cells-cap N` (default 0 = no cap) is a **skip filter**: municipalities
  whose grid exceeds N are skipped at enqueue (with a warning + count), never
  enqueued as jobs that would fail at drain time.
- Enqueue one `scrape_jobs` row per municipality: `status='pending'`,
  `params=ScrapeParams.model_dump(mode="json")`, `triggered_by='country-fanout'`.
  Reuses the existing `scrape_jobs` table — **no migration**.
- `--limit N`: enqueue only the first N (testing / population-priority slice).
- `--dry-run`: print the planned jobs (name, cells, categories) and the total
  query estimate; enqueue nothing.
- Requires `SUPABASE_URL` + `SUPABASE_SERVICE_KEY` (like `run-pending`).
- The existing `run-pending` worker (systemd timer) drains the queue unchanged.

## Data flow

```
scrape-country NL → load nl.jsonl (342, population-first)
  → per municipality: ScrapeParams(bbox, curated cats, auto max_cells)
  → INSERT scrape_jobs (pending)            [existing table]
  → run-pending workers grid-scrape each    [existing engine, unchanged]
  → leads upserted, deduped run-wide by external_id
```

## Decisions (locked)

- **JSONL** per ISO country code (clean diffs, trivial append).
- **PDOK/CBS** as seed source (validated, CC0, deterministic, offline at runtime);
  Nominatim stays only as the interactive `scrape --region` fallback.
- **Population-first enqueue** (best-effort via Wikidata; null → unordered tail).
- **No DB migration** — `scrape-country` inserts into existing `scrape_jobs`.
- **Enqueue-only** — running jobs stays `run-pending`'s job (production = systemd
  timer; local = run `run-pending` to drain). No inline runner (YAGNI).
- **Guard auto-scale only for fan-out jobs**; interactive `scrape --region` keeps
  the 300 human-footgun default.

## Explicitly OUT (Tier B / C — later)

Polygon-clipping to skip water cells (`shapely` + PDOK polygons), pre-detail
website prefilter, GeoNames completeness assertion, density-tiered cell sizes,
per-municipality coverage/refresh tracking, worker concurrency/proxy, CMS form
integration for country runs.

## Testing (TDD)

- `tests/test_regions.py`: `load_country("nl")` returns 342 entries; every `bbox`
  is a valid 4-float `(min_lat<max_lat, min_lng<max_lng)` in NL range; round-trips
  through `RegionEntry`; unknown country raises; `list_countries()` includes "nl".
- `tests/test_categories.py`: `CURATED_CATEGORIES` ⊆ `DEFAULT_CATEGORIES`, length in
  the ~18–26 band, no duplicates.
- `tests/test_cli.py` (extend): `scrape-country NL --dry-run` plans 342 jobs and
  enqueues none; `--limit 3` plans 3; `--deep` uses the full 46; each planned job's
  `ScrapeParams` has the municipality bbox, curated categories, and an auto-scaled
  `max_cells` ≥ its grid cell count (so `_build_grid_queries` won't raise); enqueue
  path inserts N rows (mocked Supabase client).
- Build tool: not unit-tested (one-time network script); its output is verified by
  the registry tests (342 lines) and a manual run.

## Definition of Done

- `mypy src` 0 errors; `ruff check .` clean; full pytest green.
- `regions/nl.jsonl` committed with exactly 342 municipalities + valid bboxes.
- `scrape-country NL --dry-run` lists 342 municipality jobs with a query estimate.
- `scrape-country NL --limit 2` enqueues 2 pending `scrape_jobs` rows that
  `run-pending` can pick up and grid-scrape.
- Large municipalities (Súdwest-Fryslân) are planned with an auto-scaled `max_cells`
  and do **not** raise `GridTooLargeError`.
- Adding a country is a drop-in `regions/<cc>.jsonl` + nothing else.
