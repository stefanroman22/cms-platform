import io

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import client, resolve


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "test-key")


def test_classify_place_id():
    assert resolve.classify("  ChIJN1t_tDeuEmsRUsoyG83frY4 ") == (
        "place_id",
        "ChIJN1t_tDeuEmsRUsoyG83frY4",
    )


def test_classify_maps_url_variants():
    for u in [
        "https://maps.app.goo.gl/Xyz123",
        "https://www.google.com/maps/place/Samir+Kapsalon/@52.5,5.47,17z/data=!3m1",
        "https://goo.gl/maps/abc",
        "https://maps.google.nl/?cid=123",
    ]:
        assert resolve.classify(u)[0] == "maps_url", u


def test_classify_text():
    assert resolve.classify("Samir Kapsalon, Lelystad") == ("text", "Samir Kapsalon, Lelystad")


def test_classify_lowercase_slug_is_text_not_place_id():
    assert resolve.classify("hairdresser-supplies-amsterdam-centrum") == (
        "text",
        "hairdresser-supplies-amsterdam-centrum",
    )


def test_classify_rejects_spoofed_google_domains():
    assert resolve.classify("https://google.com.evil.com/maps/place/x")[0] == "text"
    assert resolve.classify("https://google.evil/maps/place/x")[0] == "text"


def test_classify_accepts_regional_google_domain():
    assert resolve.classify("https://www.google.co.uk/maps/place/x")[0] == "maps_url"


def test_classify_schemeless_short_link_gets_scheme():
    assert resolve.classify("maps.app.goo.gl/Xyz123") == (
        "maps_url",
        "https://maps.app.goo.gl/Xyz123",
    )


def test_resolve_long_google_url_skips_expansion(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: None)
    monkeypatch.setattr(
        resolve, "expand_short_link", lambda url: pytest.fail("no expansion for google.com")
    )
    calls = {}

    def fake_search(query, *, lat=None, lng=None, language="en", page_size=5):
        calls.update(query=query, lat=lat, lng=lng)
        return [{"place_id": "ChIJ1", "name": "Name", "address": "A"}]

    monkeypatch.setattr(client, "text_search", fake_search)
    out = resolve.resolve("https://www.google.com/maps/place/Name/@52.5,5.47,17z")
    assert out.place_id == "ChIJ1"
    assert calls == {"query": "Name", "lat": 52.5, "lng": 5.47}


def test_extract_place_id_from_query_param():
    u = "https://www.google.com/maps/search/?api=1&query=x&query_place_id=ChIJabc_DEF-1234567890xyz"
    assert resolve.extract_place_id_from_url(u) == "ChIJabc_DEF-1234567890xyz"


def test_extract_place_id_from_data_segment():
    u = "https://www.google.com/maps/place/X/@1,2,17z/data=!4m6!3m5!1s0x47c6:0x9a!8m2!3d52!4d5!19sChIJabc-xyz_123?entry=ttu"
    assert resolve.extract_place_id_from_url(u) == "ChIJabc-xyz_123"


def test_extract_place_id_none_for_cid_only():
    assert resolve.extract_place_id_from_url("https://maps.google.com/?cid=12345") is None


def test_parse_name_and_coords():
    u = "https://www.google.com/maps/place/Samir+Kapsalon+%26+Barber/@52.5083,5.4751,17z/data=!3m1"
    assert resolve.parse_name_and_coords(u) == ("Samir Kapsalon & Barber", 52.5083, 5.4751)


def test_parse_name_and_coords_missing():
    assert resolve.parse_name_and_coords("https://maps.app.goo.gl/abc") == (None, None, None)


def test_resolve_place_id_short_circuits(monkeypatch):
    monkeypatch.setattr(client, "_urlopen", lambda *a, **k: pytest.fail("no network expected"))
    assert resolve.resolve("ChIJN1t_tDeuEmsRUsoyG83frY4") == resolve.Resolution(
        "ChIJN1t_tDeuEmsRUsoyG83frY4", []
    )


def test_resolve_url_uses_resolution_api(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: "ChIJfromapi")
    assert resolve.resolve("https://maps.app.goo.gl/abc").place_id == "ChIJfromapi"


def test_resolve_url_with_embedded_id_skips_api(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: pytest.fail("should not call"))
    u = "https://www.google.com/maps/place/X/@1,2,17z/data=!19sChIJembedded"
    assert resolve.resolve(u).place_id == "ChIJembedded"


def test_resolve_unresolvable_url_falls_back_to_text_search(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: None)
    monkeypatch.setattr(
        resolve,
        "expand_short_link",
        lambda url: ("https://www.google.com/maps/place/Samir+Kapsalon/@52.5,5.47,17z/data=!3m1"),
    )
    calls = {}

    def fake_search(query, *, lat=None, lng=None, language="en", page_size=5):
        calls.update(query=query, lat=lat, lng=lng)
        return [
            {"place_id": "ChIJ1", "name": "Samir Kapsalon", "address": "A"},
            {"place_id": "ChIJ2", "name": "Samir Barber", "address": "B"},
        ]

    monkeypatch.setattr(client, "text_search", fake_search)
    out = resolve.resolve("https://maps.app.goo.gl/dead")
    assert out.place_id is None and len(out.candidates) == 2
    assert calls == {"query": "Samir Kapsalon", "lat": 52.5, "lng": 5.47}


def test_resolve_unresolvable_url_without_name_gives_empty(monkeypatch):
    monkeypatch.setattr(client, "resolve_maps_url", lambda url: None)
    monkeypatch.setattr(resolve, "expand_short_link", lambda url: url)
    monkeypatch.setattr(client, "text_search", lambda *a, **k: pytest.fail("nothing to search"))
    assert resolve.resolve("https://maps.app.goo.gl/dead") == resolve.Resolution(None, [])


def test_resolve_text_single_hit_is_direct(monkeypatch):
    monkeypatch.setattr(
        client,
        "text_search",
        lambda *a, **k: [{"place_id": "ChIJonly", "name": "X", "address": None}],
    )
    assert resolve.resolve("Samir Kapsalon Lelystad").place_id == "ChIJonly"


def test_resolve_text_many_hits_are_candidates(monkeypatch):
    monkeypatch.setattr(
        client,
        "text_search",
        lambda *a, **k: [
            {"place_id": "a", "name": "A", "address": None},
            {"place_id": "b", "name": "B", "address": None},
        ],
    )
    out = resolve.resolve("Kapsalon")
    assert out.place_id is None and [c["place_id"] for c in out.candidates] == ["a", "b"]


def test_expand_short_link_follows_redirect(monkeypatch):
    class _R(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            pass

        def geturl(self):
            return "https://www.google.com/maps/place/X/@1,2,17z"

    monkeypatch.setattr(client, "_urlopen", lambda req, timeout: _R(b""))
    assert resolve.expand_short_link("https://maps.app.goo.gl/abc").startswith(
        "https://www.google.com/maps/place/X"
    )


def test_expand_short_link_failure_returns_input(monkeypatch):
    def boom(req, timeout):
        raise OSError("down")

    monkeypatch.setattr(client, "_urlopen", boom)
    assert resolve.expand_short_link("https://maps.app.goo.gl/abc") == "https://maps.app.goo.gl/abc"
