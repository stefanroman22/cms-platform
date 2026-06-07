# RT Scraper — Lead Coverage Improvement Plan

_Goal: search a city or region by name, with no category input, and reliably collect **all** the businesses worth pitching a website to. Quality and completeness over speed._

---

## TL;DR — the one root cause

Your scraper issues **one text search per query** (e.g. `businesses in NL`) and reads the left-hand feed. Google Maps **hard-caps that feed at ~120 results** and then shows *"You've reached the end of the list."* — no matter how big the area. Worse, your default stops at **20** (`max_results_per_area = 20`), and a country/city query has **no map-viewport control**, so Google zooms out to the whole country and returns a thin, non-exhaustive slice.

A single business works perfectly because that path (`scrape-url`) never touches the search feed. Category search "feels better" only because `restaurants in Lelystad` is narrow enough that ≤120 actually covers most of them; `businesses in NL` asks one query to cover a country.

The fix is the industry-standard pattern for exhaustive Maps harvesting: **tile the area into a geographic grid, and iterate a built-in list of business categories across every cell** — each narrow (category × small map cell) query stays under the 120 cap, and you union + dedupe the results. This is exactly how the two most popular open-source Maps scrapers solve it (omkarcloud, gosom — see Sources). You already have run-wide dedup by Google feature id, so the hardest part is done.

---

## How it works today

```
ScrapeParams(category="businesses", cities=[], max_results_per_area=20)
        │
        ▼
_build_queries()  →  ["businesses in NL"]        # 1 query for the whole country
        │
        ▼
_search_url()     →  https://www.google.com/maps/search/businesses+in+NL/?hl=en&gl=NL
        │                                         # ↑ no @lat,lng,zoom — Google picks a national viewport
        ▼
_collect_place_links()  →  scroll feed, stop at max_results (20) or end-marker
        │
        ▼
_scrape_one_place() per link  →  Lead  →  filters  →  sink
```

Every stage is sound for a *single narrow query*. The problem is purely **how many queries you issue and how each one is geographically scoped**.

---

## Root-cause diagnosis

**1. Google's ~120-results-per-search ceiling (the hard wall).**
Any single Maps search returns at most ~120 places, then ends the list. This is a Google-side limit, independent of your code. Confirmed by the omkarcloud maintainer ("the Google Maps API limits search results to 120 per query and restricts the ability to scroll beyond this number") and by Rayobyte/Apify write-ups. One query can therefore *never* enumerate a city, let alone a country.

**2. Your per-query cap is 20, not even 120.**
`ScrapeParams.max_results_per_area = 20` and CLI `--max = 20`. So today each query is throttled to 20 long before the 120 wall. A country run = ~20 leads.

**3. No map-viewport control in the search URL.**
`_search_url()` produces `/maps/search/<query>/?hl=&gl=` with **no `@lat,lng,zoom`**. Google then chooses the viewport from the text. `businesses in NL` → national viewport → sparse, capped feed. The grid fix works precisely by setting the viewport explicitly per cell (`/@52.37,4.89,16z`).

**4. The generic keyword `businesses` is a weak enumerator.**
Maps has no real "all businesses" query. `businesses in X` returns a loose, non-exhaustive mix. Reliable enumeration comes from iterating concrete categories (`hairdresser`, `plumber`, `restaurant`, …). This is why category mode already feels better — and it's the lever to pull automatically.

**5. `min_reviews = 5` (default ON) silently deletes your ideal leads.**
`ScrapeFilters.min_reviews = 5` drops every business with fewer than 5 reviews. Businesses **without a website** are disproportionately tiny — sole traders, new shops — and frequently have 0–4 reviews. So the default filter is removing exactly the segment you want. This alone can hide a large fraction of valid no-website leads.

**6. Feed scroll can stop early.**
`_collect_place_links()` scrolls by full `scrollHeight` and gives up after 3 stable rounds. Large jumps can outrun lazy loading, and obfuscated end-marker classes (`p.HlvSq`) drift. Net effect: occasionally you stop before the true end of even a sub-120 list.

---

## The fix: geographic grid × category enumeration

The user types only a place name. Everything else is generated.

```
"Amsterdam"
   │  (Nominatim / OSM → bounding box, free)
   ▼
bbox = (minLat, minLng, maxLat, maxLng)
   │  (tile into ~1–1.5 km cells)
   ▼
grid = [(lat₁,lng₁), (lat₂,lng₂), … (latₙ,lngₙ)]      # N cells
   │
   ▼  for each cell  ×  each category in CATEGORY_LIST   (M categories)
   ▼
/maps/search/<category>/@lat,lng,16z      # N×M narrow queries, each ≤120
   │
   ▼
collect links → scrape place → Lead
   │
   ▼
run-wide dedup by external_id (Google feature id)   ← you already have this
   │
   ▼
filters → sinks
```

**A. Geographic grid.** Convert the place name to a bounding box (Nominatim is free and matches your "no paid API" rule), then step across it in fixed cells. Each cell becomes an explicit `@lat,lng,zoom` viewport so Google returns *that neighbourhood's* businesses, capped at 120 — which is plenty for one ~1 km cell.

**B. Category enumeration.** Ship a built-in list of categories and iterate it per cell. The operator never types a category; the system covers them. (Commercial tools ship 4,000+ categories; you can start with ~40–80 high-value ones and grow.)

**C. Combine + dedupe.** Grids and category overlap produce duplicates by design. Your `external_id` (Google `!1s` feature id) already dedupes run-wide via `seen_ids`, including the cheap pre-visit `peek_external_id`. This is the piece most people get wrong and you already have it.

---

## Concrete code changes

### 1. `models.py` — add grid + category params

```python
class ScrapeParams(BaseModel):
    ...
    # NEW: region-first search
    region: str | None = None              # e.g. "Amsterdam" or "Noord-Holland"
    bbox: tuple[float, float, float, float] | None = None  # minLat,minLng,maxLat,maxLng
    grid_cell_km: float = 1.2              # ~1.2 km cells ≈ comfortably under 120/cell in dense areas
    grid_zoom: int = 16                    # viewport zoom per cell
    categories: list[str] = Field(default_factory=list)   # empty → DEFAULT_CATEGORIES
    max_results_per_area: int = 120        # was 20 — let each cell fill to the ceiling
```

### 2. New `geo.py` — bbox + grid (pure, unit-testable)

```python
import math

def grid_centers(min_lat, min_lng, max_lat, max_lng, cell_km=1.2):
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
```

```python
# bbox from a place name via Nominatim (free, no key). Cache results.
import urllib.parse, urllib.request, json

def bbox_for_place(name: str) -> tuple[float, float, float, float]:
    q = urllib.parse.urlencode({"q": name, "format": "json", "limit": 1})
    req = urllib.request.Request(
        f"https://nominatim.openstreetmap.org/search?{q}",
        headers={"User-Agent": "rt-scraper/1.0 (contact@romantech)"},  # Nominatim requires a UA
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        data = json.load(r)
    s, n, w, e = map(float, data[0]["boundingbox"])  # [south, north, west, east]
    return s, w, n, e
```

### 3. `categories.py` — the built-in list

```python
DEFAULT_CATEGORIES = [
    "restaurant", "cafe", "bar", "bakery", "hairdresser", "barber shop",
    "beauty salon", "nail salon", "plumber", "electrician", "carpenter",
    "painter", "roofer", "cleaning service", "landscaper", "garden center",
    "car repair", "car wash", "auto parts store", "dentist", "physiotherapist",
    "veterinarian", "florist", "butcher", "greengrocer", "clothing store",
    "shoe store", "jeweler", "optician", "pharmacy", "pet store", "bookstore",
    "hardware store", "furniture store", "bike shop", "tailor", "dry cleaner",
    "photographer", "driving school", "real estate agency", "accountant",
    "law firm", "travel agency", "gym", "yoga studio", "tattoo parlor",
    # …grow over time; this is the dial for completeness
]
```

### 4. `google_maps.py` — viewport URL + grid query loop

```python
def _search_url(query, language, country, center=None, zoom=16):
    slug = _SPACE_RE.sub("+", query.strip())
    url = f"https://www.google.com/maps/search/{slug}/"
    if center is not None:
        lat, lng = center
        url += f"@{lat},{lng},{zoom}z"        # ← explicit viewport: the key change
    return url + f"?hl={language}&gl={country}"
```

```python
def _build_grid_queries(params):
    """Yield (category, center, zoom). Region-first; falls back to legacy text mode."""
    if params.bbox or params.region:
        bbox = params.bbox or bbox_for_place(params.region)
        cats = params.categories or DEFAULT_CATEGORIES
        for center in grid_centers(*bbox, cell_km=params.grid_cell_km):
            for cat in cats:
                yield cat, center, params.grid_zoom
    else:
        for q in _build_queries(params):     # keep current behaviour as a fallback
            yield q, None, params.grid_zoom
```

Then in `scrape()`, swap the loop to iterate `_build_grid_queries`, and when a `center` is present the text query is just the bare category (the viewport supplies the geography):

```python
for cat, center, zoom in _build_grid_queries(params):
    await page.goto(_search_url(cat, params.language, params.country, center, zoom),
                    wait_until="domcontentloaded", timeout=20_000)
    ...
    links = await _collect_place_links(page, params.max_results_per_area)
    # existing per-link dedup + _scrape_one_place + filters stay exactly as-is
```

### 5. `models.py` — fix the filter that hides your targets

```python
class ScrapeFilters(BaseModel):
    min_reviews: int | None = None    # was 5 — stop deleting micro-businesses w/o websites
    web_presence: list[WebPresence] = Field(default_factory=lambda: ["none", "social_only"])
```

If you still want a floor, make it `0` and apply it consciously per job, not as a global default.

### 6. `_collect_place_links()` — scroll to the true end

Scroll in smaller steps, wait for the count to actually grow, raise the stable threshold, and detect the end-marker by **text** (multilingual) instead of a fragile class:

```python
PREV = 0
for _ in range(60):                       # generous ceiling; you don't care about speed
    anchors = await page.locator(selectors.RESULTS_ITEM_LINK).element_handles()
    # …collect hrefs as today…
    if await _feed_has_end_text(page):     # "end of the list" / "einde van de lijst"
        break
    if len(links) == PREV:
        stable += 1
        if stable >= 5: break
    else:
        stable = 0
    PREV = len(links)
    await feed.evaluate("(el) => el.scrollBy(0, el.clientHeight * 0.8)")  # 80% of a screen, not scrollHeight
    await _polite_delay()
```

---

## Quality improvements ("find all leads, correctly")

- **Drop `min_reviews=5`** (above) — the biggest single quality win for the no-website segment.
- **Verify `web_presence` edge cases.** `classify_web_presence` treats any non-social host as `has_website`. Add Google-owned booking/ordering hosts (e.g. `business.site`, `sites.google.com`, link-in-bio domains beyond the current set) so a "website" that's really a Google placeholder is still counted as `none`/`social_only` and kept as a lead.
- **Keep place pages, drop only at filter stage.** You already visit then filter — good. Consider logging *why* each lead was dropped (filter reason) so you can audit completeness.
- **Add a coverage self-check.** After a region run, log cells that hit the 120 ceiling — those are saturated and should be re-tiled smaller (cell-split). Cells far below 120 are fully covered.

---

## Running longer & safely (you don't care about speed)

- **Checkpoint per cell.** Persist completed `(cell, category)` pairs so a long region run resumes after a crash/IP block instead of restarting. Natural fit with your existing `scrape_jobs` table — store progress in `params`/a child table.
- **Pacing is already polite** (`600–2200 ms`). For multi-thousand-query region runs, add a longer jittered pause every N place-pages and rotate through the **proxy hook already stubbed in `_new_context`** if Google starts challenging the Hetzner IP.
- **Cell-split on saturation.** When a cell returns ~120 for a category, automatically subdivide that cell into 4 and re-run — guarantees you never silently lose the overflow in dense city centres.
- **Parallelism later.** Multiple contexts can run disjoint cells concurrently; correctness is unaffected because dedup is global. Add only once correctness is verified.

---

## Trade-offs & alternatives

| Approach | Coverage | Cost | Notes |
|---|---|---|---|
| **Grid × categories (recommended)** | Highest | Free (your stack) | Slow by design; reuses all your existing extraction + dedup. Best match for "quality over speed." |
| Official Places API (new) | Medium | Paid + still capped | Text/Nearby Search returns **~60 results max** per query (20×3 pages). Paying does **not** remove the need for a grid — you'd grid *and* pay. Contradicts your no-paid-API v1 rule. |
| OSM / Overpass | Variable | Free | OSM tags businesses and often has a `website`/`contact:website` tag, so it's a great **cross-source supplement** to confirm "no website" and to catch places Maps ranks low. Coverage varies by region/country. Fits your README's "additional source scrapers (OSM)" extension point. |
| Hybrid (Maps grid ∪ OSM) | Highest + verified | Free | Use OSM to seed/verify and Maps grid as the primary harvester; reconcile on name+geo. The end state. |

---

## Phased rollout

**Phase 1 — quick wins (hours).** Raise `max_results_per_area` to 120; set `min_reviews` default to `None`; harden the scroll loop. This alone meaningfully increases yield on your existing per-city/category runs with zero architectural change.

**Phase 2 — region-first grid (the core fix).** Add `geo.py` (Nominatim bbox + grid), `categories.py`, viewport `_search_url`, and `_build_grid_queries`. Now `--region Amsterdam` with no category enumerates the city. Dedup already handles the overlap.

**Phase 3 — longevity.** Per-cell checkpoint/resume, cell-split on saturation, proxy rotation. Makes multi-region/country runs survivable.

**Phase 4 — cross-source.** Add an OSM/Overpass engine emitting the same `Lead` shape; reconcile to fill gaps and double-confirm "no website."

---

## Coverage math (illustrative, orders of magnitude)

- **Today, country default:** 1 query, capped at 20 → ~20 leads for all of NL.
- **Today, one city+category:** 1 query, ≤120 → up to ~120.
- **Phase 2, a mid-size city (~5×5 km):** ~16 cells at the default 1.2 km (or ~25 cells at 1.0 km) × ~40 categories = **~640–1,000 narrow queries**, each ≤120 → tens of thousands of raw hits → deduped down to the city's true unique-business count (typically thousands). A 25×25 km metro at 1.2 km is ~440 cells. That is the difference between "20 leads" and "the whole city."

The dial you turn for completeness is **cell size** (smaller = more cells = more thorough) and **category list length**. Both trade only time — which you've said you're happy to spend.

---

## Sources

- omkarcloud/google-maps-scraper — maintainer on the 120-cap and the coords+zoom+multi-query workaround: https://github.com/omkarcloud/google-maps-scraper/discussions/132
- gosom/google-maps-scraper — explicit grid mode (`-grid-bbox`, `-grid-cell` km, `-zoom`): https://github.com/gosom/google-maps-scraper
- Rayobyte — "Scraping More Than 120 Results From Google Maps": https://rayobyte.com/university/courses/google-maps/more-than-120-results/
- Apify — "Google Places API limits (and how to overcome them)": https://blog.apify.com/google-places-api-limits/
- Nominatim API (free OSM geocoding for bounding boxes): https://nominatim.org/release-docs/latest/api/Overview/
