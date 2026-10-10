"""POST /forms/{slug}/{form_key} reads the destination email from the form's
content_entries rows. A multi-locale project has one row per locale, so the
lookup must pick a row instead of assuming exactly one."""

from auth_service.routers.forms import _destination_email


def _row(locale, published=None, draft=None):
    return {"locale": locale, "published_content": published, "draft_content": draft}


def test_single_row_uses_published_then_draft():
    assert _destination_email([_row("en", {"destination_email": "a@x.com"})], "en") == "a@x.com"
    assert _destination_email([_row("en", {}, {"destination_email": "d@x.com"})], "en") == "d@x.com"


def test_multi_locale_prefers_default_locale_row():
    rows = [
        _row("de", {"destination_email": "de@x.com"}),
        _row("ro", {"destination_email": "ro@x.com"}),
        _row("en", {"destination_email": "en@x.com"}),
    ]
    assert _destination_email(rows, "ro") == "ro@x.com"


def test_multi_locale_falls_back_to_any_configured_row():
    rows = [_row("ro", {}, {}), _row("en", {"destination_email": "en@x.com"})]
    assert _destination_email(rows, "ro") == "en@x.com"


def test_no_rows_or_no_destination_returns_none():
    assert _destination_email([], "en") is None
    assert _destination_email([_row("en", None, None)], "en") is None
