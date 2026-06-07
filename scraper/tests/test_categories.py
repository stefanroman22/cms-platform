from scraper.categories import CURATED_CATEGORIES, DEFAULT_CATEGORIES


def test_curated_is_subset_of_default():
    assert set(CURATED_CATEGORIES).issubset(set(DEFAULT_CATEGORIES))


def test_curated_no_duplicates_and_reasonable_size():
    assert len(CURATED_CATEGORIES) == len(set(CURATED_CATEGORIES))
    assert 18 <= len(CURATED_CATEGORIES) <= 26


def test_curated_drops_website_saturated_categories():
    for dropped in ("pharmacy", "law firm", "accountant", "dentist", "real estate agency"):
        assert dropped not in CURATED_CATEGORIES
