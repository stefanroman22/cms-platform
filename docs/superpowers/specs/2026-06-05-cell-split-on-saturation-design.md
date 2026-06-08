# RT Scraper — Cell-Split on Saturation (design)

**Date:** 2026-06-05
**Component:** `scraper/` (rt-scraper Python package)
**Status:** approved (brainstorming) → ready for plan
**Builds on:** region-first grid (2026-06-04) + country fan-out (2026-06-05)

## Problem & goal

Google caps a single map search at ~120 results. A grid cell denser than 120 of
the searched category returns only the top ~120 — and because no-website
businesses rank low, they are exactly the leads dropped. Smaller fixed cells
help but waste queries everywhere. **Goal:** when a cell *actually* saturates
(hits 120 without exhausting the list), subdivide just that cell into 4 quarters
at a tighter zoom and re-scrape, recursively, so dense areas are covered
completely while sparse areas stay cheap. Completeness without uniform cost.

## Key insight

Subdivision must **zoom in** (tighten the viewport), not merely place centers
closer. Each `+1` zoom quarters the viewport area, so a `zoom+1` search on each
of the 4 quarter-centers returns that quarter's own (smaller) result set. Placing
4 centers at the same zoom would just re-return the same overlapping 120.

## Decisions (locked)

- **ON by default** for all grid runs (interactive `scrape --region` and
  `scrape-country`); `--no-split` disables. `max_split_depth=0` also disables.
- **Max split depth = 2** (zoom 16→18; at a 0.6 km base that reaches ~0.15 km
  cells — below 120 even in the densest NL core).
- Splitting is **per (cell, category)** — the saturated query's category is
  preserved across its sub-cells.

## Components

### 1. `geo.split_cell(lat, lng, cell_km) -> Iterator[tuple[float, float]]` (new, pure)
Yields the 4 quarter-centers of a cell, each offset `±cell_km/4` from the parent
centre (i.e. the centre of each quarter):
```python
def split_cell(lat: float, lng: float, cell_km: float) -> Iterator[tuple[float, float]]:
    dlat = (cell_km / 4) / 111.0
    dlng = (cell_km / 4) / (111.0 * math.cos(math.radians(lat)))
    for slat in (lat - dlat, lat + dlat):
        for slng in (lng - dlng, lng + dlng):
            yield round(slat, 6), round(slng, 6)
```
Pure → unit-tested alongside `grid_centers`.

### 2. `_collect_place_links` returns `(links, saturated)`
Signature changes from `-> list[str]` to `-> tuple[list[str], bool]`.
- Track `reached_end` (set `True` when the end-marker/text break fires).
- `saturated = len(links) >= max_results and not reached_end` — Google had more
  than it showed.
- Early-return paths return the flag too: single-result redirect →
  `([page.url], False)`; no-feed → `([], False)`.
- The scroll loop body is otherwise unchanged.

### 3. `scrape()` search loop → a work-queue (`collections.deque`)
Each work item is `(query_text, center, zoom, cell_km, depth)`. The initial queue
is the existing `grid_queries` at `depth=0, cell_km=params.grid_cell_km`:
```python
work: deque[tuple[str, tuple[float, float] | None, int, float, int]] = deque(
    (q, c, z, params.grid_cell_km, 0) for q, c, z in grid_queries
)
while work:
    query_text, center, zoom, cell_km, depth = work.popleft()
    # ... goto(_search_url(query_text, lang, country, center, zoom)) + consent + delay
    links, saturated = await _collect_place_links(page, params.max_results_per_area)
    # ... the existing per-link loop (peek-dedup → _scrape_one_place → post-dedup
    #     → _passes_filters → yield) is UNCHANGED ...
    if (
        params.split_on_saturation
        and saturated
        and center is not None
        and depth < params.max_split_depth
    ):
        for sub in split_cell(center[0], center[1], cell_km):
            work.append((query_text, sub, zoom + 1, cell_km / 2, depth + 1))
```
New imports: `from collections import deque` (stdlib group), `split_cell` added to
the existing `from .geo import ...`.

### 4. `ScrapeParams` — two additive fields
```python
split_on_saturation: bool = True
max_split_depth: int = 2   # 0 = never split
```
Both are referenced in the `scrape()` loop, satisfying
`test_every_scrape_params_field_is_referenced_in_engine`. Stored as additive JSON
in `scrape_jobs.params` → no DB migration; `run-pending` round-trips them.

### 5. CLI — `--no-split` on `scrape` and `scrape-country`
`no_split: Annotated[bool, typer.Option("--no-split")] = False`, mapped via
`split_on_saturation=not no_split` into the built `ScrapeParams`. `max_split_depth`
keeps its model default (2); no CLI flag for it (YAGNI — tunable via params).

## Why all existing behavior stays intact

- **No saturation → identical to today.** When no cell hits the cap, the deque
  drains each initial query exactly once, in order — same as the current `for`
  loop. Every existing test exercises this path.
- `scrape-url` / direct-url path: untouched (returns before the search loop).
- Legacy text mode (`center is None`): never splits.
- `max_cells` guard is plan-time (`_build_grid_queries`); splits are runtime →
  no conflict. Splits are bounded: ≤ 4 + 16 = 20 extra cells per saturated cell
  at depth 2.
- Run-wide `seen_ids` dedup already collapses parent↔sub-cell overlap; splitting
  only adds previously-unseen overflow.
- `--no-split` / `max_split_depth=0` is a full off-switch.

## Testing (TDD)

- `tests/test_geo.py`: `split_cell(52.0, 5.0, 1.2)` yields 4 distinct centres, each
  within `±cell_km/4` of the parent (≈0.0027° lat), all inside the parent cell.
- `tests/test_models.py`: `ScrapeParams().split_on_saturation is True` and
  `.max_split_depth == 2`; both round-trip through `model_validate`/`model_dump`.
- `tests/test_google_maps_pure.py` (the key integration test): an async `scrape()`
  test with a fake `_collect_place_links` that returns `(links, saturated=True)` on
  the parent cell and `(links, False)` on the children. Assert: exactly **1
  `page.goto` at `16z` + 4 at `17z`** (parent saturated → 4 zoom-17 sub-cells);
  sub-cell leads are yielded; a child returning `saturated=True` at depth 1 splits
  once more then stops at `max_split_depth=2`. Also assert that with
  `split_on_saturation=False` a saturated parent produces **no** sub-cells.
  Update the existing `fake_collect_links` in
  `test_scrape_grid_mode_visits_viewport_urls_and_dedups` to return `(["link1"], False)`.
- `tests/test_cli.py`: `scrape --region X --no-split …` and
  `scrape-country NL --no-split …` build params with `split_on_saturation is False`;
  default (no flag) is `True`.

## Out of scope

Adaptive starting cell size, a per-job split budget cap, persisting split state
for resume, zoom-ceiling handling beyond depth 2 (16→18 is far under Google's
~21 max). Polygon clipping / website-prefilter remain separate Tier-B items.

## Definition of Done

- `mypy src` 0 errors; `ruff check .` clean; full pytest green (existing + new).
- A saturated cell demonstrably spawns 4 zoom-+1 sub-cells in the integration test;
  depth capped at 2; `--no-split` disables it.
- No behavioral change when nothing saturates (all prior tests pass unchanged
  except the one mock signature update).
- `scrape-country NL --category restaurant --grid-cell-km 0.6` now self-refines any
  cell that still clips, so dense cores can't silently drop leads.
