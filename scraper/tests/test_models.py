from scraper.models import Lead, ScrapeFilters, ScrapeParams


def test_scrape_params_default_construction_all_optional():
    """ScrapeParams() with no args must succeed and produce the agreed defaults."""
    p = ScrapeParams()
    assert p.category == "businesses"
    assert p.country == "NL"
    assert p.cities == []
    assert p.areas == []
    assert p.max_results_per_area == 120
    assert p.language == "en"
    assert p.lead_type == "website"
    assert p.with_reviews is True
    assert p.filters.web_presence == ["none", "social_only"]
    assert p.filters.min_rating is None
    assert p.filters.min_reviews == 3
    assert p.filters.max_rating is None


def test_scrape_params_explicit_override():
    """Explicit fields still win over defaults."""
    p = ScrapeParams(category="restaurants", country="DE", cities=["Berlin"])
    assert p.category == "restaurants"
    assert p.country == "DE"
    assert p.cities == ["Berlin"]


def test_scrape_filters_all_optional_off_by_default():
    f = ScrapeFilters()
    assert f.min_rating is None
    assert f.max_rating is None
    assert f.min_reviews == 3
    assert f.max_reviews is None
    assert f.web_presence == ["none", "social_only"]


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


def test_scrape_params_grid_defaults():
    p = ScrapeParams()
    assert p.region is None
    assert p.bbox is None
    assert p.grid_cell_km == 1.2
    assert p.grid_zoom == 16
    assert p.categories == []
    assert p.max_cells == 300


def test_scrape_params_grid_fields_roundtrip():
    p = ScrapeParams(
        region="Lelystad",
        bbox=(52.4, 5.4, 52.6, 5.6),
        grid_cell_km=1.0,
        grid_zoom=15,
        categories=["restaurant", "bakery"],
        max_cells=50,
    )
    restored = ScrapeParams.model_validate(p.model_dump())
    assert restored.region == "Lelystad"
    assert restored.bbox == (52.4, 5.4, 52.6, 5.6)
    assert restored.categories == ["restaurant", "bakery"]
    assert restored.grid_cell_km == 1.0
    assert restored.grid_zoom == 15
    assert restored.max_cells == 50


def test_lead_extra_defaults_to_empty_dict():
    lead = Lead(
        external_id="0x1234:0xabcd",
        business_name="Acme",
        name_normalized="acme",
    )
    assert lead.extra == {}
    assert lead.lead_type == "website"
    assert lead.web_presence == "unknown"
    assert lead.primary_source == "google_maps"


def test_scrape_params_split_defaults():
    p = ScrapeParams()
    assert p.split_on_saturation is True
    assert p.max_split_depth == 2


def test_scrape_params_split_fields_roundtrip():
    p = ScrapeParams(split_on_saturation=False, max_split_depth=3)
    restored = ScrapeParams.model_validate(p.model_dump())
    assert restored.split_on_saturation is False
    assert restored.max_split_depth == 3
