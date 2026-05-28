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


def test_expand_full_search_url_raises():
    """A full google.com/maps/search/... URL is structurally a Maps URL but
    not a single place — must be rejected before reaching the scraper."""
    with pytest.raises(InvalidMapsURLError, match="not a place page"):
        expand_if_short("https://www.google.com/maps/search/restaurants")
