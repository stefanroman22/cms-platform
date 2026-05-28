# Scraper Single-URL Mode Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a CLI mode that scrapes a single Google Maps business URL provided by the user, reusing the existing per-place extraction logic but bypassing the search/feed loop and category filters.

**Architecture:** Add an optional `direct_url` field to `ScrapeParams`. When set, the `scrape()` async generator short-circuits past `_build_queries` / `_search_url` / `_collect_place_links` and calls the existing `_scrape_one_place` directly. URL validation + short-link expansion live in a new pure module `urls.py`. A new Typer CLI command `scrape-url` exposes this to users. Filters are bypassed in direct-URL mode (the user explicitly chose this lead). All existing flows are unchanged.

**Tech Stack:** Python 3.11+, Pydantic v2, Playwright async API, Typer, pytest + pytest-asyncio.

---

## File Structure

| File | Action | Responsibility |
|---|---|---|
| `scraper/src/scraper/models.py` | modify | Add `direct_url: str \| None = None` field to `ScrapeParams`. |
| `scraper/src/scraper/urls.py` | **create** | Pure validation + short-link expansion (HTTP HEAD redirect follow). |
| `scraper/src/scraper/google_maps.py` | modify | `scrape()` short-circuits to single-URL path when `params.direct_url` is set. Bypass `_passes_filters` in that branch. |
| `scraper/src/scraper/cli.py` | modify | New `scrape-url` Typer command. |
| `scraper/tests/test_urls.py` | **create** | Tests for URL validation + expansion helpers. |
| `scraper/tests/test_models.py` | modify | Tests for the new `direct_url` field. |
| `scraper/tests/test_google_maps_pure.py` | modify | Test for `scrape()` short-circuit dispatch (mocking Playwright + `_scrape_one_place`). |
| `scraper/tests/test_cli.py` | **create** | Typer `CliRunner` tests for the new `scrape-url` command. |

---

## Task 1: Add `direct_url` field to `ScrapeParams`

**Files:**
- Modify: `scraper/src/scraper/models.py:28-43`
- Test: `scraper/tests/test_models.py`

- [ ] **Step 1: Write the failing test**

Add to `scraper/tests/test_models.py`:

```python
from scraper.models import ScrapeParams


def test_scrape_params_direct_url_optional_defaults_to_none():
    p = ScrapeParams()
    assert p.direct_url is None


def test_scrape_params_accepts_direct_url():
    p = ScrapeParams(direct_url="https://www.google.com/maps/place/Foo/data=!1s0x47c63f...")
    assert p.direct_url == "https://www.google.com/maps/place/Foo/data=!1s0x47c63f..."


def test_scrape_params_direct_url_with_other_fields():
    """direct_url coexists with the normal search params — same model, no separate type."""
    p = ScrapeParams(
        category="restaurants",
        country="NL",
        cities=["Lelystad"],
        direct_url="https://maps.app.goo.gl/abc",
    )
    assert p.direct_url == "https://maps.app.goo.gl/abc"
    assert p.cities == ["Lelystad"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/scraper" && source .venv/Scripts/activate && python -m pytest tests/test_models.py -v
```
Expected: 3 FAILs with `ValidationError: Extra inputs are not permitted` (because `ScrapeParams` uses `extra="forbid"`).

- [ ] **Step 3: Add the field to `ScrapeParams`**

In `scraper/src/scraper/models.py`, modify the `ScrapeParams` class (around line 28-43). Add `direct_url` as the LAST field so it's a clean append:

```python
class ScrapeParams(BaseModel):
    """Mirrors the row in scrape_jobs.params. The CMS form maps 1:1 to
    these fields; the worker deserialises and runs."""

    model_config = ConfigDict(extra="forbid")

    category: str = "businesses"
    country: str = "NL"
    cities: list[str] = Field(default_factory=list)
    areas: list[str] = Field(default_factory=list)
    max_results_per_area: int = 20
    language: str = "en"
    lead_type: LeadType = "website"
    with_reviews: bool = True
    review_limit: int = 10
    filters: ScrapeFilters = Field(default_factory=ScrapeFilters)
    # Single-URL mode. When set, the scrape engine skips the search/feed
    # loop and visits this URL directly. Used by the `scrape-url` CLI
    # command. Filters are bypassed in this mode — the user explicitly
    # chose this lead.
    direct_url: str | None = None
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_models.py -v
```
Expected: all PASS (including any pre-existing model tests).

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run:
```bash
python -m pytest tests/ -v
```
Expected: all PASS. Specifically `test_pipeline.py` still passes — it uses `ScrapeParams(category="x", country="NL")` which doesn't touch the new field.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/models.py scraper/tests/test_models.py
git commit -m "feat(scraper): add direct_url field to ScrapeParams for single-URL mode"
```

---

## Task 2: Create `urls.py` — validation + expansion helpers

**Files:**
- Create: `scraper/src/scraper/urls.py`
- Create: `scraper/tests/test_urls.py`

- [ ] **Step 1: Write the failing tests**

Create `scraper/tests/test_urls.py`:

```python
"""Offline tests for URL helpers — pure validation + HTTP-mocked expansion."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from scraper.urls import InvalidMapsURLError, expand_if_short, is_google_maps_url


# ─── is_google_maps_url ─────────────────────────────────────────────────


def test_valid_full_place_url():
    url = "https://www.google.com/maps/place/Caffe+Lentini/@52.5,5.4,15z/data=!1s0x47c63f..."
    assert is_google_maps_url(url) is True


def test_valid_short_url_maps_app_goo_gl():
    assert is_google_maps_url("https://maps.app.goo.gl/abc123") is True


def test_valid_legacy_goo_gl_maps():
    assert is_google_maps_url("https://goo.gl/maps/xyz789") is True


def test_valid_with_www_prefix_stripped():
    assert is_google_maps_url("https://google.com/maps/place/Foo") is True


def test_rejects_non_maps_google_url():
    assert is_google_maps_url("https://www.google.com/search?q=restaurants") is False


def test_rejects_unrelated_domain():
    assert is_google_maps_url("https://example.com/maps") is False


def test_rejects_empty_string():
    assert is_google_maps_url("") is False


def test_rejects_garbage():
    assert is_google_maps_url("not a url at all") is False


# ─── expand_if_short ────────────────────────────────────────────────────


def test_expand_pass_through_full_url():
    """Full place URLs are returned unchanged — no HTTP call."""
    url = "https://www.google.com/maps/place/Foo/data=!1s0x47c63f..."
    with patch("scraper.urls.urllib.request.urlopen") as fake_open:
        result = expand_if_short(url)
    assert result == url
    fake_open.assert_not_called()


def test_expand_short_url_follows_redirect():
    """maps.app.goo.gl URLs are expanded by following the Location header."""
    expanded = "https://www.google.com/maps/place/Foo/data=!1s0x47c63f..."
    fake_resp = MagicMock()
    fake_resp.geturl.return_value = expanded
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = None

    with patch("scraper.urls.urllib.request.urlopen", return_value=fake_resp):
        result = expand_if_short("https://maps.app.goo.gl/abc123")
    assert result == expanded


def test_expand_short_url_raises_on_non_place_redirect():
    """If a short URL resolves to a search page (not a place), reject."""
    fake_resp = MagicMock()
    fake_resp.geturl.return_value = "https://www.google.com/maps/search/restaurants"
    fake_resp.__enter__.return_value = fake_resp
    fake_resp.__exit__.return_value = None

    with patch("scraper.urls.urllib.request.urlopen", return_value=fake_resp):
        with pytest.raises(InvalidMapsURLError, match="not a place"):
            expand_if_short("https://maps.app.goo.gl/abc123")


def test_expand_rejects_non_maps_input():
    with pytest.raises(InvalidMapsURLError, match="not a Google Maps URL"):
        expand_if_short("https://example.com/foo")
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_urls.py -v
```
Expected: `ModuleNotFoundError: No module named 'scraper.urls'`.

- [ ] **Step 3: Create the `urls.py` module**

Create `scraper/src/scraper/urls.py`:

```python
"""URL helpers — validation + short-link expansion.

Separated from dedup.py because expand_if_short does HTTP IO and dedup.py
is intentionally IO-free."""

from __future__ import annotations

import urllib.request
from urllib.parse import urlparse

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

    # Full URLs need no expansion.
    if host not in _SHORT_HOSTS:
        return url

    # Short link — follow redirect.
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "rt-scraper/1.0"},
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=_EXPAND_TIMEOUT_S) as resp:
        final = resp.geturl()

    # After expansion, confirm we landed on a place page.
    if "/place/" not in final and "!1s" not in final:
        raise InvalidMapsURLError(
            f"short URL resolved to a non-place page (not a single business): {final!r}"
        )
    return final
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_urls.py -v
```
Expected: all 11 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add scraper/src/scraper/urls.py scraper/tests/test_urls.py
git commit -m "feat(scraper): add urls module for maps URL validation + short-link expansion"
```

---

## Task 3: Short-circuit `scrape()` when `direct_url` is set

**Files:**
- Modify: `scraper/src/scraper/google_maps.py:541-607`
- Test: `scraper/tests/test_google_maps_pure.py`

- [ ] **Step 1: Write the failing tests**

Add to `scraper/tests/test_google_maps_pure.py`:

```python
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.google_maps import scrape
from scraper.models import Lead, ScrapeParams


def _stub_lead() -> Lead:
    return Lead(
        external_id="0x47c63f:0xabc",
        business_name="Caffe Lentini",
        name_normalized="caffe lentini",
        web_presence="none",
    )


@pytest.mark.asyncio
async def test_scrape_direct_url_skips_search_and_yields_one_lead(monkeypatch):
    """When direct_url is set: no query loop, no feed scroll, one place visit."""
    params = ScrapeParams(
        direct_url="https://www.google.com/maps/place/Caffe+Lentini/data=!1s0x47c63f:0xabc"
    )

    build_queries_calls: list = []
    collect_links_calls: list = []
    scrape_one_calls: list[str] = []

    def fake_build_queries(p):
        build_queries_calls.append(p)
        return ["should not be called"]

    async def fake_collect_links(page, max_results):
        collect_links_calls.append(max_results)
        return ["should not be called"]

    async def fake_scrape_one(ctx, url, p, job_id):
        scrape_one_calls.append(url)
        return _stub_lead()

    monkeypatch.setattr("scraper.google_maps._build_queries", fake_build_queries)
    monkeypatch.setattr("scraper.google_maps._collect_place_links", fake_collect_links)
    monkeypatch.setattr("scraper.google_maps._scrape_one_place", fake_scrape_one)
    monkeypatch.setattr("scraper.google_maps.expand_if_short", lambda u: u)

    # Stub Playwright so no real browser is launched.
    fake_browser = AsyncMock()
    fake_ctx = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_ctx)
    fake_pw_chromium = AsyncMock()
    fake_pw_chromium.launch = AsyncMock(return_value=fake_browser)
    fake_pw = MagicMock()
    fake_pw.chromium = fake_pw_chromium
    fake_pw_cm = AsyncMock()
    fake_pw_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_pw_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper.google_maps.async_playwright", return_value=fake_pw_cm):
        leads = [lead async for lead in scrape(params)]

    assert len(leads) == 1
    assert leads[0].external_id == "0x47c63f:0xabc"
    # Search path was NOT exercised.
    assert build_queries_calls == []
    assert collect_links_calls == []
    # Single place visit using the user-supplied URL.
    assert scrape_one_calls == [params.direct_url]


@pytest.mark.asyncio
async def test_scrape_direct_url_bypasses_filters(monkeypatch):
    """When direct_url is set, _passes_filters must NOT be called — the
    user explicitly chose this lead; do not silently filter it out."""
    params = ScrapeParams(
        direct_url="https://www.google.com/maps/place/Foo/data=!1s0x1:0x2",
        filters={"min_reviews": 9999},  # would normally reject everything
    )

    filter_calls: list = []

    def fake_passes_filters(lead, f):
        filter_calls.append((lead.external_id, f))
        return True

    async def fake_scrape_one(ctx, url, p, job_id):
        # Return a lead that would FAIL the filter (review_count below min).
        return Lead(
            external_id="0x1:0x2",
            business_name="x",
            name_normalized="x",
            review_count=1,
        )

    monkeypatch.setattr("scraper.google_maps._scrape_one_place", fake_scrape_one)
    monkeypatch.setattr("scraper.google_maps._passes_filters", fake_passes_filters)
    monkeypatch.setattr("scraper.google_maps.expand_if_short", lambda u: u)

    fake_browser = AsyncMock()
    fake_ctx = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_ctx)
    fake_pw_chromium = AsyncMock()
    fake_pw_chromium.launch = AsyncMock(return_value=fake_browser)
    fake_pw = MagicMock()
    fake_pw.chromium = fake_pw_chromium
    fake_pw_cm = AsyncMock()
    fake_pw_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_pw_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper.google_maps.async_playwright", return_value=fake_pw_cm):
        leads = [lead async for lead in scrape(params)]

    assert len(leads) == 1
    assert filter_calls == []  # filter MUST NOT be called in direct_url mode


@pytest.mark.asyncio
async def test_scrape_direct_url_expands_short_url(monkeypatch):
    """maps.app.goo.gl URLs are expanded before being visited."""
    params = ScrapeParams(direct_url="https://maps.app.goo.gl/abc123")
    expanded = "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2"

    expand_calls: list[str] = []
    scrape_one_calls: list[str] = []

    def fake_expand(u):
        expand_calls.append(u)
        return expanded

    async def fake_scrape_one(ctx, url, p, job_id):
        scrape_one_calls.append(url)
        return _stub_lead()

    monkeypatch.setattr("scraper.google_maps.expand_if_short", fake_expand)
    monkeypatch.setattr("scraper.google_maps._scrape_one_place", fake_scrape_one)

    fake_browser = AsyncMock()
    fake_ctx = AsyncMock()
    fake_browser.new_context = AsyncMock(return_value=fake_ctx)
    fake_pw_chromium = AsyncMock()
    fake_pw_chromium.launch = AsyncMock(return_value=fake_browser)
    fake_pw = MagicMock()
    fake_pw.chromium = fake_pw_chromium
    fake_pw_cm = AsyncMock()
    fake_pw_cm.__aenter__ = AsyncMock(return_value=fake_pw)
    fake_pw_cm.__aexit__ = AsyncMock(return_value=None)

    with patch("scraper.google_maps.async_playwright", return_value=fake_pw_cm):
        leads = [lead async for lead in scrape(params)]

    assert expand_calls == ["https://maps.app.goo.gl/abc123"]
    assert scrape_one_calls == [expanded]
    assert len(leads) == 1
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_google_maps_pure.py -v
```
Expected: the 3 new tests FAIL (either `ImportError` for `expand_if_short` not yet imported in `google_maps.py`, or `AssertionError` because the search path runs anyway).

- [ ] **Step 3: Add the import + short-circuit branch in `scrape()`**

In `scraper/src/scraper/google_maps.py`:

3a. Add the import at the top of the file (next to the other relative imports):

```python
from .urls import expand_if_short
```

3b. Replace the body of `scrape()` (currently lines 541-607). Keep the function signature and the playwright/browser setup identical; insert a single-URL branch BEFORE the query loop:

```python
async def scrape(
    params: ScrapeParams,
    scrape_job_id: str | None = None,
    headless: bool | None = None,
) -> AsyncIterator[Lead]:
    """Top-level async generator. Yields Lead objects one at a time so
    sinks can stream and the pipeline can update counters in real time.

    When `params.direct_url` is set: skip the search/feed loop entirely
    and visit only that URL. Filters are bypassed — the caller explicitly
    chose this lead via the `scrape-url` CLI command.
    """
    use_headless = settings.SCRAPER_HEADLESS if headless is None else headless

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=use_headless,
            args=["--disable-blink-features=AutomationControlled"],
        )
        ctx = await _new_context(browser, params.language, params.country)
        page = await ctx.new_page()

        try:
            # ─── Single-URL mode ───────────────────────────────────────
            if params.direct_url:
                expanded = expand_if_short(params.direct_url)
                logger.info("direct-url scrape: {}", expanded)
                try:
                    lead = await _scrape_one_place(ctx, expanded, params, scrape_job_id)
                except Exception as exc:  # noqa: BLE001 — surface but don't crash sinks
                    logger.warning("direct-url place {} failed: {}", expanded, exc)
                    return
                if lead is not None:
                    yield lead
                return

            # ─── Search-feed mode (unchanged) ──────────────────────────
            # Run-wide dedup so cartesian queries (cities × areas) and overlapping
            # neighbourhoods don't yield the same business twice. Peek the feature
            # id BEFORE visiting to save the ~5-10s place-page cost.
            seen_ids: set[str] = set()
            for query in _build_queries(params):
                logger.info("query: {}", query)
                await page.goto(
                    _search_url(query, params.language, params.country),
                    wait_until="domcontentloaded",
                    timeout=20_000,
                )
                await _accept_consent(page)
                await _polite_delay()

                links = await _collect_place_links(page, params.max_results_per_area)
                logger.info("collected {} place links for {!r}", len(links), query)

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
        finally:
            await ctx.close()
            await browser.close()
```

- [ ] **Step 4: Run the new tests to verify they pass**

Run:
```bash
python -m pytest tests/test_google_maps_pure.py -v
```
Expected: all PASS (including pre-existing tests like `test_build_queries_*`).

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run:
```bash
python -m pytest tests/ -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/google_maps.py scraper/tests/test_google_maps_pure.py
git commit -m "feat(scraper): short-circuit scrape() to single URL when direct_url is set"
```

---

## Task 4: Add `scrape-url` CLI command

**Files:**
- Modify: `scraper/src/scraper/cli.py` (add new command after the `scrape` command)
- Test: `scraper/tests/test_cli.py` (new file)

- [ ] **Step 1: Write the failing tests**

Create `scraper/tests/test_cli.py`:

```python
"""CLI tests for scrape-url. Uses typer.testing.CliRunner; mocks pipeline."""

from __future__ import annotations

from unittest.mock import patch

from typer.testing import CliRunner

from scraper.cli import app
from scraper.pipeline import Counters

runner = CliRunner()


def test_scrape_url_dry_run_builds_params_with_direct_url(tmp_path):
    out = tmp_path / "lead.json"

    captured_params = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured_params.append(params)
        return Counters(found=1, inserted=1, skipped=0)

    with patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline):
        result = runner.invoke(
            app,
            [
                "scrape-url",
                "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2",
                "--dry-run",
                "--out",
                str(out),
            ],
        )

    assert result.exit_code == 0, result.stdout
    assert len(captured_params) == 1
    assert captured_params[0].direct_url == "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2"
    # Counters echoed as JSON on the last line.
    assert '"found": 1' in result.stdout
    assert '"inserted": 1' in result.stdout


def test_scrape_url_rejects_non_maps_url():
    result = runner.invoke(
        app,
        ["scrape-url", "https://example.com/foo", "--dry-run"],
    )
    assert result.exit_code != 0
    assert "Google Maps" in result.stdout or "Google Maps" in str(result.exception)


def test_scrape_url_default_sinks_skip_sheet(tmp_path):
    """For single-URL mode, the default sinks should be Supabase only —
    no Sheets append (one-row appends are noisy). Dry-run overrides this."""
    captured_sinks = []

    async def fake_run_pipeline(params, sinks, scrape_job_id=None):
        captured_sinks.append([type(s).__name__ for s in sinks])
        return Counters(found=1, inserted=1, skipped=0)

    # Not dry-run — go through the real-sink path.
    with (
        patch("scraper.cli.run_pipeline", side_effect=fake_run_pipeline),
        patch("scraper.cli.SupabaseSink"),
        patch("scraper.cli.SheetsSink") as sheet_class,
    ):
        result = runner.invoke(
            app,
            ["scrape-url", "https://www.google.com/maps/place/Foo/data=!1s0x1:0x2"],
        )

    assert result.exit_code == 0, result.stdout
    sheet_class.assert_not_called()  # Sheets sink not constructed by default
```

- [ ] **Step 2: Run tests to verify they fail**

Run:
```bash
python -m pytest tests/test_cli.py -v
```
Expected: 3 FAILs — `No such command 'scrape-url'`.

- [ ] **Step 3: Add the `scrape-url` command to `cli.py`**

In `scraper/src/scraper/cli.py`:

3a. Add a new import next to the existing imports:

```python
from .urls import InvalidMapsURLError, is_google_maps_url
```

3b. Add a new helper `_build_sinks_single` near the existing `_build_sinks` (it differs in that the Sheets sink is opt-in, not opt-out):

```python
def _build_sinks_single(
    *, dry_run: bool, supabase: bool, sheet: bool, out_path: Path | None
) -> list[Sink]:
    """Sinks for single-URL mode. Defaults differ from `_build_sinks`:
    Sheets is opt-in (one-row appends are noisy and rarely useful)."""
    sinks: list[Sink] = []
    if dry_run:
        sinks.append(JsonSink(out_path or Path("./lead-single.json")))
        return sinks
    if supabase:
        sinks.append(SupabaseSink())
    if sheet:
        sinks.append(SheetsSink())
    if not sinks:
        raise typer.BadParameter("at least one sink required (Supabase, sheet, or --dry-run)")
    return sinks
```

3c. Add the new command, immediately after the existing `@app.command()` `scrape` function (around line 96):

```python
@app.command("scrape-url")
def scrape_url(
    url: Annotated[str, typer.Argument(help="Google Maps URL of a single business.")],
    dry_run: Annotated[bool, typer.Option("--dry-run")] = False,
    no_headless: Annotated[bool, typer.Option("--no-headless")] = False,
    no_supabase: Annotated[bool, typer.Option("--no-supabase")] = False,
    sheet: Annotated[bool, typer.Option("--sheet")] = False,
    out: Annotated[Path | None, typer.Option("--out")] = None,
    language: Annotated[str, typer.Option("--language")] = "en",
    country: Annotated[str, typer.Option("--country")] = "NL",
) -> None:
    """Scrape a single business by Google Maps URL.

    Useful for ad-hoc lead lookup and for testing the extraction pipeline
    against a known place page without running a full search.
    """
    if not is_google_maps_url(url):
        raise typer.BadParameter(
            f"not a Google Maps URL: {url!r}. Expected google.com/maps/..., "
            "maps.app.goo.gl/..., or goo.gl/maps/..."
        )

    params = ScrapeParams(
        country=country,
        language=language,
        direct_url=url,
    )
    sinks = _build_sinks_single(
        dry_run=dry_run, supabase=not no_supabase, sheet=sheet, out_path=out
    )
    if no_headless:
        settings.SCRAPER_HEADLESS = False

    try:
        counters = asyncio.run(run_pipeline(params, sinks))
    except InvalidMapsURLError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.echo(json.dumps(counters.__dict__))
```

- [ ] **Step 4: Run tests to verify they pass**

Run:
```bash
python -m pytest tests/test_cli.py -v
```
Expected: all 3 PASS.

- [ ] **Step 5: Run the full test suite to confirm no regressions**

Run:
```bash
python -m pytest tests/ -v
```
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add scraper/src/scraper/cli.py scraper/tests/test_cli.py
git commit -m "feat(scraper): add scrape-url CLI command for single-business scrapes"
```

---

## Task 5: Manual end-to-end smoke test

**Goal:** Verify the new CLI works against a real Google Maps URL.

**Files:** None modified — this task is manual verification.

- [ ] **Step 1: Pick a known business**

Open Google Maps in a browser, search for any business with a Google Maps profile that has reviews + hours + a known web presence (a Lelystad café you've used during prior scrape testing is fine). Click the Share button → "Copy link." You'll get either a full URL or a `maps.app.goo.gl/...` short link — both should work.

- [ ] **Step 2: Run a dry-run scrape against that URL**

Run:
```bash
cd "c:/Users/stefa/.gemini/antigravity/scratch/CMS - websites/scraper" && source .venv/Scripts/activate && python -m scraper.cli scrape-url "<paste URL here>" --dry-run --no-headless
```

`--no-headless` lets you watch Chromium drive the page; remove it for unattended runs.

Expected:
- Browser opens, navigates to the place page, accepts consent if shown, clicks reviews/hours/about tabs, then closes.
- Console prints one log line: `direct-url scrape: <expanded URL>`.
- Final line is JSON: `{"found": 1, "inserted": 1, "skipped": 0}` (or `inserted: 0` if the JsonSink wrote OK but the lead is otherwise empty — see step 3).

- [ ] **Step 3: Inspect the JSON output**

Run:
```bash
cat ./lead-single.json
```

Expected: a JSON file containing one Lead row with at minimum `business_name`, `address`, `rating`, `review_count`, `opening_hours`, `web_presence`, and (if present on Maps) `reviews` with up to 3 entries.

If any expected field is missing or `null` when you can see it on the actual Maps page, that's a selector issue — log a follow-up but don't block the merge.

- [ ] **Step 4: Run again against a short URL**

If your first URL was full, try once more with a `maps.app.goo.gl/...` link to exercise the expansion path.

Run:
```bash
python -m scraper.cli scrape-url "https://maps.app.goo.gl/<short>" --dry-run
```

Expected: same output as step 3 — the expansion happens transparently.

- [ ] **Step 5: Try an invalid URL**

Run:
```bash
python -m scraper.cli scrape-url "https://example.com/foo" --dry-run
```

Expected: exit code != 0, error message containing "not a Google Maps URL".

- [ ] **Step 6: Note any issues found**

If everything passed, no commit needed. If you spotted a bug (e.g., a field that should be populated wasn't), file it as a follow-up — do not bundle the fix into this PR.

---

## Task 6: Update the scraper README

**Files:**
- Modify: `scraper/README.md`

- [ ] **Step 1: Add a `scrape-url` section under the existing CLI heading**

In `scraper/README.md`, after the existing `### scrape` section (around line 63), insert:

```markdown
### scrape-url

Scrape a single business by its Google Maps URL. Useful for ad-hoc lead lookup or for verifying the extraction pipeline against a known place page.

```bash
python -m scraper.cli scrape-url "https://maps.app.goo.gl/abc123" --dry-run
```

Accepts full URLs (`google.com/maps/place/...`), legacy short links (`goo.gl/maps/...`), and mobile share links (`maps.app.goo.gl/...`). Short links are expanded automatically.

Defaults differ from `scrape`: Sheets sink is opt-in (`--sheet`) because appending a single row to a multi-thousand-row mirror is rarely useful. Supabase is used by default; pass `--no-supabase` to skip it.

Filters from the search-mode `scrape` command are bypassed — the user has explicitly chosen this lead, so it is always written to the configured sinks.
```

- [ ] **Step 2: Commit**

```bash
git add scraper/README.md
git commit -m "docs(scraper): document scrape-url CLI command"
```

---

## Self-Review Notes

**Spec coverage:**
- ✅ Single-URL scrape feature → Tasks 1-4
- ✅ Reuses existing extraction (`_scrape_one_place` unchanged) → Task 3
- ✅ Bypasses filters when URL is explicitly provided → Task 3, test 2
- ✅ Validates URL is a Maps URL → Tasks 2 + 4
- ✅ Supports short URLs via expansion → Task 2 + test 3 in Task 3
- ✅ Works as CLI feature (not just test harness) → Task 4
- ✅ Dry-run support for testing → Task 4 default path
- ✅ Real-world smoke test → Task 5
- ✅ Documentation → Task 6

**Out of scope (intentional):**
- Backend `/admin/scrape-jobs` endpoint for single-URL jobs — current need is CLI-only; queue plumbing is a future task if the feature gets used often.
- A chat-driven UI ("Scrape information for this lead: <url>") — that's an agent-layer concern; the CLI command is the underlying primitive it would call.
- Proxy routing — explicitly deferred per user note ("invest in the proxy later").

**Risks:**
- The `expand_if_short` HTTP call happens BEFORE the browser launches. If the user has no network, they get a clearer error than from Playwright. ✅
- Short links sometimes resolve to non-place pages (e.g., a search). The validation in `expand_if_short` catches this. ✅
- `_scrape_one_place` is decorated with `@retry(stop_after_attempt(3))`. In single-URL mode, a failure still retries 3× before giving up — desirable. ✅
