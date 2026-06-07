"""Offline tests for pure helpers inside google_maps.py — no Playwright."""

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from scraper.google_maps import (
    _about_available,
    _build_queries,
    _group_about_items,
    _parse_hours_pairs,
    _parse_rating,
    _parse_review_count,
    _parse_star_rating,
    _passes_filters,
    _search_url,
    _split_address,
    _strip_icon_prefix,
    _with_hl,
    scrape,
)
from scraper.models import Lead, ScrapeFilters, ScrapeParams


def _mk_lead(**kw):
    base = {
        "external_id": "x",
        "business_name": "x",
        "name_normalized": "x",
        "web_presence": "none",
    }
    base.update(kw)
    return Lead(**base)


def test_build_queries_country_only():
    p = ScrapeParams(category="restaurants", country="NL")
    assert _build_queries(p) == ["restaurants in NL"]


def test_build_queries_cities_no_areas():
    p = ScrapeParams(category="restaurants", country="NL", cities=["Lelystad", "Almere"])
    assert _build_queries(p) == [
        "restaurants in Lelystad",
        "restaurants in Almere",
    ]


def test_build_queries_cities_and_areas():
    p = ScrapeParams(
        category="hair salons",
        country="NL",
        cities=["Lelystad"],
        areas=["Centrum", "Zuiderpark"],
    )
    assert _build_queries(p) == [
        "hair salons in Centrum, Lelystad",
        "hair salons in Zuiderpark, Lelystad",
    ]


def test_search_url_encodes_spaces_and_passes_locale():
    url = _search_url("hair salons in Lelystad", language="nl", country="NL")
    assert url == "https://www.google.com/maps/search/hair+salons+in+Lelystad/?hl=nl&gl=NL"


def test_split_address_with_postal():
    pc, city = _split_address("Some Street 5, 8232 BD Lelystad")
    assert pc == "8232 BD"
    assert city == "Lelystad"


def test_split_address_without_postal():
    pc, city = _split_address("Some Square 7, Lelystad")
    assert pc is None
    assert city == "Lelystad"


def test_split_address_empty():
    assert _split_address(None) == (None, None)
    assert _split_address("") == (None, None)


def test_parse_rating():
    assert _parse_rating("4.3") == 4.3
    assert _parse_rating("4,3") == 4.3  # NL locale comma
    assert _parse_rating(None) is None
    assert _parse_rating("n/a") is None


def test_parse_review_count():
    # Rating decimal must not be concatenated with the count.
    assert _parse_review_count("4.3 stars, 187 reviews") == 187
    assert _parse_review_count("187 reviews") == 187
    assert _parse_review_count(None) is None
    assert _parse_review_count("no digits") is None


def test_strip_icon_prefix_removes_pua_then_newline():
    assert _strip_icon_prefix("\nDe Waag 9, 8232 DX Lelystad") == "De Waag 9, 8232 DX Lelystad"


def test_strip_icon_prefix_removes_pua_for_phone():
    assert _strip_icon_prefix("\n0320 240 000") == "0320 240 000"


def test_strip_icon_prefix_passthrough_clean_text():
    assert _strip_icon_prefix("Restaurant Name") == "Restaurant Name"


def test_strip_icon_prefix_none():
    assert _strip_icon_prefix(None) is None


def test_strip_icon_prefix_empty_after_strip_returns_none():
    assert _strip_icon_prefix("\n    ") is None


def test_split_address_dutch_postal_code():
    # Should yield postal=8232 DX, city=Lelystad — not the previous "DX Lelystad".
    result = _split_address("De Waag 9, 8232 DX Lelystad")
    assert result == ("8232 DX", "Lelystad")


def test_parse_review_count_strips_rating_decimal():
    # aria-label like "4.7 stars 87 Reviews" — should return 87, not 4787.
    assert _parse_review_count("4.7 stars 87 Reviews") == 87


def test_parse_review_count_integer_only():
    assert _parse_review_count("87 Reviews") == 87


def test_parse_review_count_european_decimal():
    # "4,7 stars 12 reviews" — comma decimal still works because the regex pulls digits only.
    assert _parse_review_count("4,7 stars 12 reviews") == 12


def test_parse_review_count_none_label():
    assert _parse_review_count(None) is None


def test_parse_review_count_no_digits():
    assert _parse_review_count("Reviews") is None


def test_parse_review_count_parenthesised_from_rating_block():
    # F7nice container inner_text often reads "4.7\n(87)" — fallback path.
    assert _parse_review_count("4.7\n(87)") == 87
    assert _parse_review_count("4.7 (1,234)") == 1234


def test_parse_review_count_rating_only_returns_none():
    # No parens, no "review" word — must refuse to guess (avoid returning 7).
    assert _parse_review_count("4.7") is None
    assert _parse_review_count("4.7\n") is None


def test_select_reviews_prefers_five_then_backfills_four():
    from scraper.google_maps import _select_reviews

    # newest-first candidates (each already ≥4-star with text)
    cands = [
        {"rating": 4, "text": "a"},
        {"rating": 5, "text": "b"},
        {"rating": 4, "text": "c"},
        {"rating": 5, "text": "d"},
        {"rating": 4, "text": "e"},
    ]
    out = _select_reviews(cands, limit=3)
    # 5-star first in newest order (b, d), then backfill newest 4-star (a)
    assert [x["text"] for x in out] == ["b", "d", "a"]


def test_select_reviews_all_five_keeps_newest_three():
    from scraper.google_maps import _select_reviews

    cands = [{"rating": 5, "text": t} for t in ["a", "b", "c", "d"]]
    assert [x["text"] for x in _select_reviews(cands, 3)] == ["a", "b", "c"]


def test_select_reviews_only_four_when_no_five():
    from scraper.google_maps import _select_reviews

    cands = [{"rating": 4, "text": "a"}, {"rating": 4, "text": "b"}]
    assert [x["text"] for x in _select_reviews(cands, 3)] == ["a", "b"]


def test_select_reviews_empty_and_under_limit():
    from scraper.google_maps import _select_reviews

    assert _select_reviews([], 3) == []
    one = [{"rating": 5, "text": "only"}]
    assert [x["text"] for x in _select_reviews(one, 3)] == ["only"]


def test_filters_default_keeps_no_website_and_social_only():
    # Override min_reviews=None to isolate the web_presence dimension under test.
    f = ScrapeFilters(min_reviews=None)
    assert _passes_filters(_mk_lead(web_presence="none"), f) is True
    assert _passes_filters(_mk_lead(web_presence="social_only"), f) is True
    assert _passes_filters(_mk_lead(web_presence="has_website"), f) is False


def test_filters_rating_range():
    # Override min_reviews=None to isolate the rating dimension under test.
    f = ScrapeFilters(min_rating=4.0, max_rating=4.5, min_reviews=None)
    assert _passes_filters(_mk_lead(rating=4.2), f) is True
    assert _passes_filters(_mk_lead(rating=3.9), f) is False
    assert _passes_filters(_mk_lead(rating=4.6), f) is False
    # Missing rating treated as 0 → fails min_rating.
    assert _passes_filters(_mk_lead(rating=None), f) is False


def test_filters_default_skips_under_3_reviews():
    # Default review floor is 3: skip 0-2 review (and unparseable) listings.
    f = ScrapeFilters()
    assert _passes_filters(_mk_lead(web_presence="none", review_count=3), f) is True
    assert _passes_filters(_mk_lead(web_presence="none", review_count=2), f) is False
    assert _passes_filters(_mk_lead(web_presence="none", review_count=None), f) is False


def test_filters_review_count_range():
    f = ScrapeFilters(min_reviews=10, max_reviews=100)
    assert _passes_filters(_mk_lead(review_count=50), f) is True
    assert _passes_filters(_mk_lead(review_count=5), f) is False
    assert _passes_filters(_mk_lead(review_count=200), f) is False


def test_default_opening_hours_has_seven_days():
    from scraper.google_maps import _default_opening_hours

    hours = _default_opening_hours()
    assert set(hours.keys()) == {
        "Monday",
        "Tuesday",
        "Wednesday",
        "Thursday",
        "Friday",
        "Saturday",
        "Sunday",
    }
    assert all(v == "___" for v in hours.values())


def test_parse_star_rating():
    assert _parse_star_rating("5 stars") == 5
    assert _parse_star_rating("1 star") == 1
    assert _parse_star_rating("4,0 sterren") == 4  # NL aria fallback
    assert _parse_star_rating(None) is None
    assert _parse_star_rating("no number here") is None


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
    # Single place visit using the canonicalised user-supplied URL.
    from scraper.urls import canonicalize_place_url

    assert scrape_one_calls == [canonicalize_place_url(params.direct_url)]


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
    # Expanded, then canonicalised to the minimal place URL before visiting.
    from scraper.urls import canonicalize_place_url

    assert scrape_one_calls == [canonicalize_place_url(expanded)]
    assert len(leads) == 1


def test_with_hl_adds_param_when_absent():
    out = _with_hl("https://www.google.com/maps/place/X/data=!1s0x1:0x2", "en")
    assert "hl=en" in out
    assert out.startswith("https://www.google.com/maps/place/X/data=!1s0x1:0x2")


def test_with_hl_overrides_existing_hl_and_keeps_other_params():
    out = _with_hl("https://www.google.com/maps/place/X/data=!1s0x1?hl=nl&entry=ttu", "en")
    assert "hl=en" in out
    assert "hl=nl" not in out
    assert "entry=ttu" in out


def test_with_hl_preserves_data_path_segment():
    out = _with_hl("https://www.google.com/maps/place/Foo/data=!4m6!3m5!1s0xabc:0xdef", "en")
    assert "data=!4m6!3m5!1s0xabc:0xdef" in out
    assert out.endswith("hl=en")


def test_parse_hours_pairs_basic():
    out = _parse_hours_pairs(["Thursday, 12–7 pm", "Monday, Closed", "Saturday, 9 am–5 pm"])
    assert out["Thursday"] == "12–7 pm"
    assert out["Monday"] == "Closed"
    assert out["Saturday"] == "9 am–5 pm"
    assert out["Sunday"] == "___"


def test_parse_hours_pairs_split_daily_hours_keeps_full_value():
    out = _parse_hours_pairs(["Monday, 9 am–12 pm, 1–5 pm"])
    assert out["Monday"] == "9 am–12 pm, 1–5 pm"


def test_parse_hours_pairs_returns_none_when_nothing_maps():
    assert _parse_hours_pairs([]) is None
    assert _parse_hours_pairs(["garbage with no comma"]) is None


def test_about_available_from_aria():
    assert _about_available("Has in-store shopping") is True
    assert _about_available("Accepts credit cards") is True
    assert _about_available("Good for quick visit") is True
    assert _about_available("No delivery") is False
    assert _about_available("No toilet") is False


def test_group_about_items_groups_by_section_and_flags():
    items = [
        {
            "section": "Service options",
            "label": "In-store shopping",
            "aria": "Has in-store shopping",
        },
        {"section": "Service options", "label": "Delivery", "aria": "No delivery"},
        {"section": "Amenities", "label": "Toilet", "aria": "No toilet"},
    ]
    out = _group_about_items(items)
    assert out["Service options"]["In-store shopping"] is True
    assert out["Service options"]["Delivery"] is False
    assert out["Amenities"]["Toilet"] is False


def test_group_about_items_skips_empty_labels():
    out = _group_about_items([{"section": "X", "label": "", "aria": "Has x"}])
    assert out == {}


def test_every_scrape_params_field_is_referenced_in_engine():
    """Every attribute on ScrapeParams must be read somewhere in google_maps.py
    by name. Catches the "added a knob but forgot to wire it" bug."""
    import inspect

    from scraper import google_maps

    # review_limit is a no-op since reviews are fixed at the 3 newest >=4-star reviews
    # kept on the model for API compatibility. All other fields must be wired.
    whitelist = {"review_limit"}
    engine_src = inspect.getsource(google_maps)
    missing: list[str] = []

    for field_name in ScrapeParams.model_fields:
        if field_name in whitelist:
            continue
        if field_name == "filters":
            for sub in ScrapeFilters.model_fields:
                if sub not in engine_src:
                    missing.append(f"filters.{sub}")
            continue
        if field_name not in engine_src:
            missing.append(field_name)

    assert not missing, (
        f"ScrapeParams fields not referenced in scraper.google_maps: {missing}. "
        "Either wire them into the engine, or add to the whitelist with rationale."
    )


def test_text_has_end_sentinel_matches_known_phrases():
    from scraper.google_maps import _text_has_end_sentinel

    assert _text_has_end_sentinel("You've reached the end of the list.") is True
    assert _text_has_end_sentinel("foo Je hebt het EINDE van de lijst bereikt bar") is True
    assert _text_has_end_sentinel("ENDE DER LISTE") is True
    assert _text_has_end_sentinel("more results loading") is False
    assert _text_has_end_sentinel("") is False


def test_search_url_legacy_no_center_unchanged():
    url = _search_url("restaurants in Lelystad", language="nl", country="NL")
    assert url == "https://www.google.com/maps/search/restaurants+in+Lelystad/?hl=nl&gl=NL"


def test_search_url_with_center_embeds_viewport():
    url = _search_url("restaurant", "en", "NL", center=(52.5, 5.47), zoom=16)
    assert url == "https://www.google.com/maps/search/restaurant/@52.5,5.47,16z?hl=en&gl=NL"


def test_build_grid_queries_bbox_mode_counts():
    from scraper.geo import grid_centers
    from scraper.google_maps import _build_grid_queries

    p = ScrapeParams(
        bbox=(52.0, 5.0, 52.045, 5.073), categories=["restaurant", "bakery"], grid_cell_km=1.0
    )
    plan = _build_grid_queries(p)
    n_cells = len({c for _q, c, _z in plan})
    # Tie the plan's cell count to an independent grid computation.
    assert n_cells == len(list(grid_centers(52.0, 5.0, 52.045, 5.073, cell_km=1.0)))
    assert len(plan) == n_cells * 2
    assert all(z == 16 for _q, _c, z in plan)
    assert {q for q, _c, _z in plan} == {"restaurant", "bakery"}


def test_build_grid_queries_region_geocodes(monkeypatch):
    import scraper.google_maps as gm
    from scraper.config import settings
    from scraper.google_maps import _build_grid_queries

    calls = []

    def fake_bbox(name, *, cache_path):
        calls.append((name, cache_path))
        return (52.0, 5.0, 52.01, 5.01)

    monkeypatch.setattr(gm, "bbox_for_place", fake_bbox)
    p = ScrapeParams(region="Lelystad", categories=["x"], grid_cell_km=1.0)
    plan = _build_grid_queries(p)

    assert len(calls) == 1
    assert calls[0][0] == "Lelystad"
    assert calls[0][1] == Path(settings.SCRAPER_GEOCODE_CACHE)
    assert len(plan) >= 1
    assert all(q == "x" for q, _c, _z in plan)


def test_build_grid_queries_max_cells_zero_is_unlimited():
    from scraper.google_maps import _build_grid_queries

    # A box that tiles to >300 cells must NOT raise when max_cells=0.
    p = ScrapeParams(bbox=(52.0, 5.0, 52.3, 5.3), grid_cell_km=1.0, max_cells=0, categories=["x"])
    plan = _build_grid_queries(p)
    assert len(plan) > 300


@pytest.mark.asyncio
async def test_feed_has_end_text_count_zero_and_sentinel():
    from scraper.google_maps import _feed_has_end_text

    # No feed present (count==0) → False.
    empty_loc = MagicMock()
    empty_loc.count = AsyncMock(return_value=0)
    empty_page = MagicMock()
    empty_page.locator = MagicMock(return_value=empty_loc)
    assert await _feed_has_end_text(empty_page) is False

    # Feed text carries a sentinel → True.
    loc = MagicMock()
    loc.count = AsyncMock(return_value=1)
    loc.inner_text = AsyncMock(return_value="bla You've reached the end of the list.")
    page = MagicMock()
    page.locator = MagicMock(return_value=loc)
    assert await _feed_has_end_text(page) is True


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


@pytest.mark.asyncio
async def test_scrape_grid_mode_visits_viewport_urls_and_dedups(monkeypatch):
    """End-to-end grid loop: one viewport-scoped page.goto per (cell × category),
    and run-wide seen_ids dedup unions identical businesses across cells."""
    # bbox tiles to exactly 2 cells (2 lat rows × 1 lng col) at 1.0 km.
    params = ScrapeParams(
        bbox=(52.0, 5.0, 52.02, 5.01), categories=["restaurant"], grid_cell_km=1.0
    )

    async def fake_collect_links(page, max_results):
        return ["link1"], False

    async def fake_scrape_one(ctx, url, p, job_id):
        # Same external_id from every cell → dedup must collapse to one lead.
        # review_count=5 clears the default min_reviews=3 floor (test targets dedup).
        return Lead(
            external_id="dup",
            business_name="B",
            name_normalized="b",
            web_presence="none",
            review_count=5,
        )

    async def fake_polite():
        return None

    monkeypatch.setattr("scraper.google_maps._collect_place_links", fake_collect_links)
    monkeypatch.setattr("scraper.google_maps._scrape_one_place", fake_scrape_one)
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

    with patch("scraper.google_maps.async_playwright", return_value=fake_pw_cm):
        leads = [lead async for lead in scrape(params)]

    # Cross-cell dedup → one lead despite two cells surfacing the same business.
    assert len(leads) == 1
    # One scoped page.goto per (cell × category) = 2, each carrying a viewport.
    goto_urls = [call.args[0] for call in fake_page.goto.await_args_list]
    assert len(goto_urls) == 2
    for url in goto_urls:
        assert "@" in url and "16z" in url and "restaurant" in url


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
        external_id="dup",
        business_name="B",
        name_normalized="b",
        web_presence="none",
        review_count=5,
    )


@pytest.mark.asyncio
async def test_scrape_splits_saturated_cell_into_zoom_plus_one_subcells(monkeypatch):
    # tiny bbox -> exactly one parent cell (midpoint), one category
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
        bbox=(52.0, 5.0, 52.004, 5.004),
        categories=["restaurant"],
        grid_cell_km=1.0,
        max_split_depth=2,
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
        bbox=(52.0, 5.0, 52.004, 5.004),
        categories=["restaurant"],
        grid_cell_km=1.0,
        split_on_saturation=False,
    )

    async def collect(page, max_results):
        return ["x"], True  # saturated, but splitting is off

    fake_page = _stub_playwright(monkeypatch, collect, _one_lead)
    [lead async for lead in scrape(params)]

    urls = [c.args[0] for c in fake_page.goto.await_args_list]
    assert len(urls) == 1  # only the parent; no sub-cells
