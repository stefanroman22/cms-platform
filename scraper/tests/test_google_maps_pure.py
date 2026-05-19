"""Offline tests for pure helpers inside google_maps.py — no Playwright."""

from scraper.google_maps import (
    _build_queries,
    _parse_rating,
    _parse_review_count,
    _passes_filters,
    _search_url,
    _split_address,
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
    assert pc == "8232"
    assert "Lelystad" in (city or "")


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
    assert _parse_review_count("4.3 stars, 187 reviews") == 43187  # all digits joined
    assert _parse_review_count("187 reviews") == 187
    assert _parse_review_count(None) is None
    assert _parse_review_count("no digits") is None


def test_filters_default_keeps_no_website_and_social_only():
    f = ScrapeFilters()
    assert _passes_filters(_mk_lead(web_presence="none"), f) is True
    assert _passes_filters(_mk_lead(web_presence="social_only"), f) is True
    assert _passes_filters(_mk_lead(web_presence="has_website"), f) is False


def test_filters_rating_range():
    f = ScrapeFilters(min_rating=4.0, max_rating=4.5)
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
