# RT Scraper — Cell-Split on Saturation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** When a grid cell saturates (hits Google's ~120 cap without exhausting the list), subdivide it into 4 quarter-cells at zoom+1 and re-scrape, recursively up to depth 2, so dense areas are covered completely while sparse areas stay cheap.

**Architecture:** A pure `split_cell` geo helper computes the 4 quarter-centres; `_collect_place_links` reports whether it saturated; the `scrape()` search loop becomes a `deque` work-queue that pushes 4 zoom+1 sub-cells when a cell saturates. Default ON (`--no-split` / `max_split_depth=0` disables). No behavior change when nothing saturates.

**Tech Stack:** Python 3.11, Playwright (async), Pydantic v2, Typer, pytest, mypy strict, ruff.

> **Commit gate (Stefan's standing rule):** Do NOT `git commit` until Stefan says so. Keep `mypy src` + full pytest green at every task boundary.

> **Run from `scraper/`:** tests `./.venv/Scripts/python.exe -m pytest -q` · types `./.venv/Scripts/python.exe -m mypy src` · lint `./.venv/Scripts/python.exe -m ruff check .`

---

## File Structure
- Modify: `src/scraper/geo.py` — add pure `split_cell`.
- Modify: `src/scraper/models.py` — add `split_on_saturation`, `max_split_depth`.
- Modify: `src/scraper/google_maps.py` — `_collect_place_links` returns `(links, saturated)`; `scrape()` loop → work-queue + split.
- Modify: `src/scraper/cli.py` — `--no-split` on `scrape` + `scrape-country`.
- Modify: `tests/test_geo.py`, `tests/test_models.py`, `tests/test_google_maps_pure.py`, `tests/test_cli.py`.

---

## Task 1: `geo.split_cell` (pure)

**Files:** Modify `src/scraper/geo.py`; Modify `tests/test_geo.py`

- [ ] **Step 1: Write the failing test** — append to `tests/test_geo.py`:
```python
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
```

- [ ] **Step 2: Run — expect ImportError**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_geo.py::test_split_cell_yields_four_distinct_quarter_centers -q`
Expected: FAIL — cannot import `split_cell`

- [ ] **Step 3: Add `split_cell`** to `src/scraper/geo.py`, immediately after `grid_centers`:
```python
def split_cell(lat: float, lng: float, cell_km: float) -> Iterator[tuple[float, float]]:
    """Yield the 4 quarter-centres of a cell, each offset ±cell_km/4 from the
    parent centre. Used to subdivide a saturated cell at a tighter zoom."""
    dlat = (cell_km / 4) / 111.0
    dlng = (cell_km / 4) / (111.0 * math.cos(math.radians(lat)))
    for slat in (lat - dlat, lat + dlat):
        for slng in (lng - dlng, lng + dlng):
            yield round(slat, 6), round(slng, 6)
```
(`Iterator` and `math` are already imported in `geo.py`.)

- [ ] **Step 4: Run — expect PASS + mypy clean**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_geo.py -q && ./.venv/Scripts/python.exe -m mypy src`
Expected: PASS; `Success`

- [ ] **Step 5 (commit — on go-ahead):**
```bash
git add scraper/src/scraper/geo.py scraper/tests/test_geo.py
git commit -m "feat(scraper): add split_cell geo helper for cell subdivision"
```

---

## Task 2: Engine core — saturation flag, split fields, work-queue loop

**Files:** Modify `src/scraper/models.py`, `src/scraper/google_maps.py`; Modify `tests/test_models.py`, `tests/test_google_maps_pure.py`

This task changes the model, the engine, and two test files together so the suite stays green (the field-reference invariant couples the new `ScrapeParams` fields to their use in `google_maps.py`).

- [ ] **Step 1: Add the model defaults test** — append to `tests/test_models.py`:
```python
def test_scrape_params_split_defaults():
    p = ScrapeParams()
    assert p.split_on_saturation is True
    assert p.max_split_depth == 2


def test_scrape_params_split_fields_roundtrip():
    p = ScrapeParams(split_on_saturation=False, max_split_depth=3)
    restored = ScrapeParams.model_validate(p.model_dump())
    assert restored.split_on_saturation is False
    assert restored.max_split_depth == 3
```

- [ ] **Step 2: Add the integration tests** — append to `tests/test_google_maps_pure.py`. These use the same Playwright-stub shape as the existing `test_scrape_grid_mode_visits_viewport_urls_and_dedups`:
```python
def _stub_playwright(monkeypatch, collect_links, scrape_one):
    """Wire fakes for an async scrape() run and return the fake page."""
    async def fake_polite():
        return None

    monkeypatch.setattr("scraper.google_maps._collect_place_links", collect_links)
    monkeypatch.setattr("scraper.google_maps._scrape_one_place", scrape_one)
    monkeypatch.setattr("scraper.google_maps._polite_delay", fake_polite)
    monkeypatch.setattr("scraper.google_maps._accept_consent", AsyncMock())

    fake_page = AsyncMock()
    fake_ctx = AsyncMock()
    fake_ctx.new_page = AsyncMock(return_value=fake_page)
    fake_browser = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_ctx)
    fake_pw_chromium = AsyncMock()
    fake_pw_chromium.launch = AsyncMock(return_value=fake_browser)
    fake_pw = MagicMock()
    fake_pw.chromium = fake_pw_chromium
    fake_pw_cm = AsyncMock()
    fake_pw_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_pw_cm.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr("scraper.google_maps.async_playwright", lambda: fake_pw_cm)
    return fake_page


async def _one_lead(ctx, url, p, job_id):
    return Lead(
        external_id="dup", business_name="B", name_normalized="b",
        web_presence="none", review_count=5,
    )


@pytest.mark.asyncio
async def test_scrape_splits_saturated_cell_into_zoom_plus_one_subcells(monkeypatch):
    # tiny bbox → exactly one parent cell (midpoint), one category
    params = ScrapeParams(
        bbox=(52.0, 5.0, 52.004, 5.004), categories=["restaurant"], grid_cell_km=1.0
    )
    state = {"n": 0}

    async def collect(page, max_results):
        state["n"] += 1
        return [f"link{state['n']}"], state["n"] == 1  # only the parent saturates

    fake_page = _stub_playwright(monkeypatch, collect, _one_lead)
    [lead async for lead in scrape(params)]

    urls = [c.args[0] for c in fake_page.goto.await_args_list]
    assert sum("16z" in u for u in urls) == 1  # parent
    assert sum("17z" in u for u in urls) == 4  # 4 zoom+1 sub-cells
    assert len(urls) == 5


@pytest.mark.asyncio
async def test_scrape_split_respects_max_depth(monkeypatch):
    params = ScrapeParams(
        bbox=(52.0, 5.0, 52.004, 5.004), categories=["restaurant"],
        grid_cell_km=1.0, max_split_depth=2,
    )

    async def collect(page, max_results):
        return ["x"], True  # everything saturates

    fake_page = _stub_playwright(monkeypatch, collect, _one_lead)
    [lead async for lead in scrape(params)]

    urls = [c.args[0] for c in fake_page.goto.await_args_list]
    assert sum("16z" in u for u in urls) == 1
    assert sum("17z" in u for u in urls) == 4
    assert sum("18z" in u for u in urls) == 16  # depth 2
    assert len(urls) == 21  # depth-2 cells do NOT split further


@pytest.mark.asyncio
async def test_scrape_no_split_when_disabled(monkeypatch):
    params = ScrapeParams(
        bbox=(52.0, 5.0, 52.004, 5.004), categories=["restaurant"],
        grid_cell_km=1.0, split_on_saturation=False,
    )

    async def collect(page, max_results):
        return ["x"], True  # saturated, but splitting is off

    fake_page = _stub_playwright(monkeypatch, collect, _one_lead)
    [lead async for lead in scrape(params)]

    urls = [c.args[0] for c in fake_page.goto.await_args_list]
    assert len(urls) == 1  # only the parent; no sub-cells
```

- [ ] **Step 3: Run the new tests — expect FAIL** (fields missing; `_collect_place_links` not yet a tuple; no split logic)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_models.py tests/test_google_maps_pure.py -q -k "split or saturated"`
Expected: FAIL

- [ ] **Step 4: Add the `ScrapeParams` fields** in `src/scraper/models.py`, after `max_cells`:
```python
    split_on_saturation: bool = True
    max_split_depth: int = 2  # 0 = never split; recursion bound for cell-split
```

- [ ] **Step 5: Update `google_maps.py` imports.** Add `from collections import deque` to the stdlib group (before `from collections.abc import AsyncIterator`), and add `split_cell` to the geo import:
```python
from .geo import bbox_for_place, grid_centers, split_cell
```

- [ ] **Step 6: Change `_collect_place_links` to return `(links, saturated)`.** Replace the whole function with:
```python
async def _collect_place_links(page: Page, max_results: int) -> tuple[list[str], bool]:
    """Scroll the left feed until end-marker, stable count, or max reached.

    Returns (up to max_results distinct place URLs, saturated). `saturated` is
    True when the cap was hit without reaching the end of the list — Google had
    more results than it showed, so the cell should be subdivided."""
    links: list[str] = []
    seen: set[str] = set()
    stable_rounds = 0
    last_count = 0
    reached_end = False

    feed = page.locator(selectors.RESULTS_FEED)
    try:
        await feed.wait_for(timeout=8000)
    except Exception:
        # Single-result redirect: Google sent us straight to a place page.
        if "/place/" in page.url:
            return [page.url], False
        return [], False

    while len(links) < max_results and stable_rounds < 5:
        anchors = await page.locator(selectors.RESULTS_ITEM_LINK).element_handles()
        for a in anchors:
            href = await a.get_attribute("href")
            if href and href not in seen:
                seen.add(href)
                links.append(href)
                if len(links) >= max_results:
                    break

        end_marker = page.locator(selectors.RESULTS_END_MARKER)
        if await end_marker.count() > 0 or await _feed_has_end_text(page):
            logger.debug("reached end-of-list marker")
            reached_end = True
            break

        if len(links) == last_count:
            stable_rounds += 1
        else:
            stable_rounds = 0
        last_count = len(links)

        await feed.evaluate("(el) => el.scrollBy(0, Math.floor(el.clientHeight * 0.8))")
        await _polite_delay()

    saturated = len(links) >= max_results and not reached_end
    return links[:max_results], saturated
```

- [ ] **Step 7: Rewrite the `scrape()` search-feed loop** as a work-queue. Replace the block that currently starts at `seen_ids: set[str] = set()` and runs through the `for query_text, center, zoom in grid_queries:` loop (everything down to and including the inner `for link in links:` loop and its trailing `await _polite_delay()`) with:
```python
            seen_ids: set[str] = set()
            work: deque[tuple[str, tuple[float, float] | None, int, float, int]] = deque(
                (q, c, z, params.grid_cell_km, 0) for q, c, z in grid_queries
            )
            while work:
                query_text, center, zoom, cell_km, depth = work.popleft()
                logger.info("query: {!r} @ {} (depth {})", query_text, center, depth)
                await page.goto(
                    _search_url(query_text, params.language, params.country, center, zoom),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await _accept_consent(page)
                await _polite_delay()

                links, saturated = await _collect_place_links(page, params.max_results_per_area)
                logger.info(
                    "collected {} place links for {!r} (saturated={})",
                    len(links),
                    query_text,
                    saturated,
                )

                for link in links:
                    # Pre-visit dedup: if URL carries a Google feature id and we
                    # already yielded that business in this run, skip without
                    # loading the page.
                    pre_id = peek_external_id(link)
                    if pre_id is not None and pre_id in seen_ids:
                        logger.debug("dedup pre-visit skip: {}", pre_id)
                        continue

                    try:
                        lead = await _scrape_one_place(ctx, link, params, scrape_job_id)
                    except Exception as exc:  # noqa: BLE001 — per-place isolation
                        logger.warning("place {} failed: {}", link, exc)
                        continue

                    if lead is None:
                        continue
                    # Post-visit safety net for URLs whose feature id was
                    # absent at pre-visit time (hash-fallback path).
                    if lead.external_id in seen_ids:
                        logger.debug("dedup post-visit skip: {}", lead.external_id)
                        continue
                    if not _passes_filters(lead, params.filters):
                        continue

                    seen_ids.add(lead.external_id)
                    yield lead
                    await _polite_delay()

                # Cell-split: a saturated viewport cell (not legacy text mode) is
                # subdivided into 4 quarter-cells at a tighter zoom, up to depth.
                if (
                    params.split_on_saturation
                    and saturated
                    and center is not None
                    and depth < params.max_split_depth
                ):
                    subs = list(split_cell(center[0], center[1], cell_km))
                    logger.info(
                        "cell saturated → splitting into {} sub-cells (depth {}→{})",
                        len(subs),
                        depth,
                        depth + 1,
                    )
                    for sub in subs:
                        work.append((query_text, sub, zoom + 1, cell_km / 2, depth + 1))
```

- [ ] **Step 8: Update the existing grid e2e test mock.** In `tests/test_google_maps_pure.py`, in `test_scrape_grid_mode_visits_viewport_urls_and_dedups`, the `fake_collect_links` currently returns `["link1"]`; change it to return a tuple:
```python
    async def fake_collect_links(page, max_results):
        return ["link1"], False
```

- [ ] **Step 9: Run the full suite + mypy + ruff**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; ruff clean; ALL tests PASS (incl. `test_every_scrape_params_field_is_referenced_in_engine`)

- [ ] **Step 10 (commit — on go-ahead):**
```bash
git add scraper/src/scraper/models.py scraper/src/scraper/google_maps.py scraper/tests/test_models.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): cell-split on saturation (work-queue + zoom-in subdivision)"
```

---

## Task 3: CLI `--no-split`

**Files:** Modify `src/scraper/cli.py`; Modify `tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests** — append to `tests/test_cli.py`:
```python
def test_scrape_country_no_split_flag():
    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app, ["scrape-country", "NL", "--no-split", "--category", "restaurant", "--limit", "1"]
        )
    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["split_on_saturation"] is False


def test_scrape_country_split_on_by_default():
    captured = {}
    with (
        patch("scraper.cli.load_country", return_value=_fake_entries()),
        patch("scraper.cli.create_client", return_value=_fake_sb(captured)),
        patch("scraper.cli.settings") as st,
    ):
        st.SUPABASE_URL = "x"
        st.SUPABASE_SERVICE_KEY = "y"
        result = runner.invoke(
            app, ["scrape-country", "NL", "--category", "restaurant", "--limit", "1"]
        )
    assert result.exit_code == 0, result.stdout
    assert captured["rows"][0]["params"]["split_on_saturation"] is True


def test_scrape_region_no_split_flag(tmp_path):
    captured = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured.append(params)
        return Counters()

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape", "--region", "Lelystad", "--no-split",
                "--dry-run", "--no-supabase", "--out", str(tmp_path / "o.json"),
            ],
        )
    assert result.exit_code == 0, result.stdout
    assert captured[0].split_on_saturation is False
```

- [ ] **Step 2: Run — expect FAIL** (`--no-split` unknown)

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q -k "no_split or split_on_by_default"`
Expected: FAIL

- [ ] **Step 3: Add `--no-split` to the `scrape` command.** In `cli.py`, add to the `scrape` signature (after `no_supabase`):
```python
    no_split: Annotated[bool, typer.Option("--no-split")] = False,
```
and in its `ScrapeParams(...)` construction, add (after `max_cells=max_cells,`):
```python
        split_on_saturation=not no_split,
```

- [ ] **Step 4: Add `--no-split` to the `scrape-country` command.** Add to its signature (after `max_cells_cap`):
```python
    no_split: Annotated[bool, typer.Option("--no-split")] = False,
```
and in its `ScrapeParams(...)` construction, add (after `max_cells=cells,`):
```python
            split_on_saturation=not no_split,
```

- [ ] **Step 5: Run — expect PASS**

Run: `./.venv/Scripts/python.exe -m pytest tests/test_cli.py -q`
Expected: PASS

- [ ] **Step 6: Full gate**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy clean; ruff clean; ALL tests PASS

- [ ] **Step 7 (commit — on go-ahead):**
```bash
git add scraper/src/scraper/cli.py scraper/tests/test_cli.py
git commit -m "feat(scraper): --no-split flag on scrape + scrape-country"
```

---

## Task 4: Verification

- [ ] **Step 1: Full automated gate**

Run: `./.venv/Scripts/python.exe -m mypy src && ./.venv/Scripts/python.exe -m ruff check . && ./.venv/Scripts/python.exe -m pytest -q`
Expected: mypy `Success`; ruff clean; all tests PASS.

- [ ] **Step 2: Behavior smoke (no browser)** — confirm a country plan still builds and split defaults are present:

Run: `./.venv/Scripts/python.exe -c "from scraper.models import ScrapeParams; p=ScrapeParams(); print(p.split_on_saturation, p.max_split_depth)"`
Expected: `True 2`

- [ ] **Step 3: Adversarial review** — dispatch subagents/Workflow to check the diff vs spec: (a) no behavior change when `saturated=False` (work-queue ≡ old for-loop); (b) split math (`split_cell` offsets, zoom+1, cell_km/2, depth+1); (c) legacy text mode `center is None` never splits; (d) `--no-split` / `max_split_depth=0` fully disable; (e) `scrape-url` + dedup + filters untouched; (f) mypy/ruff/tests green.

---

## Self-Review (completed during planning)

**Spec coverage:** `split_cell` (Task 1) ✓; `_collect_place_links` tuple + saturated flag (Task 2 step 6) ✓; work-queue + split logic + depth cap (Task 2 step 7) ✓; `ScrapeParams` fields (Task 2 step 4) ✓; CLI `--no-split` both commands (Task 3) ✓; no-DB-migration (additive JSON) ✓; tests for split/depth/disabled/geo/model/CLI ✓; "intact when no saturation" guaranteed by the unchanged inner loop + `saturated=False` path (Task 2 step 8 keeps the existing e2e test green).

**Placeholder scan:** none — full code in every step.

**Type consistency:** `split_cell(lat, lng, cell_km) -> Iterator[tuple[float,float]]`; `_collect_place_links -> tuple[list[str], bool]`; work item `tuple[str, tuple[float,float]|None, int, float, int]`; `split_on_saturation: bool`, `max_split_depth: int` — consistent across geo/engine/model/CLI/tests.
