from scraper.dedup import classify_web_presence, external_id_from_url, normalize_name


def test_normalize_strips_accents_punctuation_case():
    assert normalize_name("Café  L'Étoile, B.V.") == "cafe l etoile b v"


def test_normalize_collapses_whitespace():
    assert normalize_name("  Multiple   Spaces  Here  ") == "multiple spaces here"


def test_normalize_handles_empty():
    assert normalize_name("") == ""


def test_external_id_from_google_feature_id():
    url = "https://www.google.com/maps/place/Cafe/@52.5,4.5,17z/data=!4m6!3m5!1s0x47c5e1234abcdef:0xfedcba9876543210!8m2!3d52.5!4d4.5"
    assert external_id_from_url(url) == "0x47c5e1234abcdef:0xfedcba9876543210"


def test_external_id_fallback_uses_normalized_identity():
    eid = external_id_from_url(
        url="https://www.google.com/maps/place/something",
        normalized_name="cafe l etoile",
        city="lelystad",
        lat=52.5123456,
        lng=5.4789012,
    )
    assert eid.startswith("hash:")
    assert len(eid) > 8


def test_external_id_fallback_deterministic():
    """Same identity inputs must produce the same hash."""
    eid1 = external_id_from_url(
        url="https://example.com/a",
        normalized_name="acme",
        city="lelystad",
        lat=52.5,
        lng=5.5,
    )
    eid2 = external_id_from_url(
        url="https://example.com/b",  # different URL
        normalized_name="acme",
        city="lelystad",
        lat=52.5,
        lng=5.5,
    )
    assert eid1 == eid2


def test_external_id_fallback_last_ditch_when_no_normalized():
    """When normalized_name is missing, hash the URL itself."""
    eid = external_id_from_url(url="https://example.com/x")
    assert eid.startswith("hash:")


def test_classify_no_url_is_none():
    assert classify_web_presence(None) == ("none", None, None)


def test_classify_empty_url_is_none():
    assert classify_web_presence("") == ("none", None, None)


def test_classify_facebook():
    presence, fb, ig = classify_web_presence("https://www.facebook.com/acme")
    assert presence == "social_only"
    assert fb == "https://www.facebook.com/acme"
    assert ig is None


def test_classify_instagram():
    presence, fb, ig = classify_web_presence("https://www.instagram.com/acme/")
    assert presence == "social_only"
    assert ig == "https://www.instagram.com/acme/"
    assert fb is None


def test_classify_linktree():
    presence, fb, ig = classify_web_presence("https://linktr.ee/acme")
    assert presence == "social_only"
    assert fb is None
    assert ig is None


def test_classify_has_website():
    presence, fb, ig = classify_web_presence("https://acme.example.com")
    assert presence == "has_website"
    assert fb is None
    assert ig is None


def test_classify_with_www_prefix_strip():
    presence, _, _ = classify_web_presence("https://www.acme.example.com")
    assert presence == "has_website"


def test_peek_external_id_extracts_feature_id():
    from scraper.dedup import peek_external_id

    url = "https://www.google.com/maps/place/X/data=!4m7!3m6!1s0x47c627aca6eb87c7:0xa8baaf0585fae425!8m2!3d52.5174668!4d5.4861178"
    assert peek_external_id(url) == "0x47c627aca6eb87c7:0xa8baaf0585fae425"


def test_peek_external_id_returns_none_without_feature_segment():
    from scraper.dedup import peek_external_id

    assert peek_external_id("https://www.google.com/maps/place/X") is None


def test_parse_latlng_extracts_floats():
    from scraper.dedup import parse_latlng_from_url

    url = "https://www.google.com/maps/place/X/data=!1s0x...!8m2!3d52.5174668!4d5.4861178"
    lat, lng = parse_latlng_from_url(url)
    assert lat == 52.5174668
    assert lng == 5.4861178


def test_parse_latlng_returns_none_when_absent():
    from scraper.dedup import parse_latlng_from_url

    assert parse_latlng_from_url("https://example.com") == (None, None)


def test_external_id_uses_full_hash_when_latlng_present():
    """The fallback hash should incorporate lat/lng when provided — two
    same-name same-city businesses at different coords get different IDs."""
    from scraper.dedup import external_id_from_url

    a = external_id_from_url(
        "https://x/a", normalized_name="subway", city="lelystad", lat=52.50, lng=5.47
    )
    b = external_id_from_url(
        "https://x/b", normalized_name="subway", city="lelystad", lat=52.60, lng=5.50
    )
    assert a != b
