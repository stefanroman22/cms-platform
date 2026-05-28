"""Offline tests for pure helpers inside google_maps.py — no Playwright."""

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
