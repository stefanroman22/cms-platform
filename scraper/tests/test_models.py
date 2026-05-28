from scraper.models import Lead, ScrapeFilters, ScrapeParams


def test_scrape_params_default_construction_all_optional():
    """ScrapeParams() with no args must succeed and produce the agreed defaults."""
    p = ScrapeParams()
    assert p.category == "businesses"
    assert p.country == "NL"
    assert p.cities == []
    assert p.areas == []
    assert p.max_results_per_area == 20
    assert p.language == "en"
    assert p.lead_type == "website"
    assert p.with_reviews is True
    assert p.filters.web_presence == ["none", "social_only"]
    assert p.filters.min_rating is None
    assert p.filters.min_reviews == 5
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
    assert f.min_reviews == 5
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
