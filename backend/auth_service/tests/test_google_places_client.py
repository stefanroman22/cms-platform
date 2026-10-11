import io
import json
import urllib.error

import pytest

from auth_service.core.config import settings
from auth_service.services.google_places import client


class _Resp(io.BytesIO):
    def __init__(self, body: bytes, headers: dict | None = None):
        super().__init__(body)
        self.headers = headers or {}

    def __enter__(self):
        return self

    def __exit__(self, *a):
        self.close()


@pytest.fixture(autouse=True)
def _key(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "test-key")


def test_place_details_sends_key_and_field_mask(monkeypatch):
    seen = {}

    def fake(req, timeout):
        seen["url"] = req.full_url
        seen["headers"] = {k.lower(): v for k, v in req.header_items()}
        return _Resp(json.dumps({"id": "ChIJx", "displayName": {"text": "Acme"}}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    place = client.place_details("ChIJx", language="nl")
    assert place["displayName"]["text"] == "Acme"
    assert seen["url"] == "https://places.googleapis.com/v1/places/ChIJx?languageCode=nl"
    assert seen["headers"]["x-goog-api-key"] == "test-key"
    assert seen["headers"]["x-goog-fieldmask"] == client.PLACE_FIELD_MASK
    assert "photos" in client.PLACE_FIELD_MASK and "editorialSummary" in client.PLACE_FIELD_MASK


def test_missing_key_raises_503(monkeypatch):
    monkeypatch.setattr(settings, "GOOGLE_MAPS_API_KEY", "")
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 503


def test_http_error_maps_to_google_error(monkeypatch):
    body = json.dumps({"error": {"message": "API key not valid", "status": "PERMISSION_DENIED"}})

    def fake(req, timeout):
        raise urllib.error.HTTPError(req.full_url, 403, "Forbidden", {}, io.BytesIO(body.encode()))

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 403
    assert "API key not valid" in ei.value.message


def test_url_error_maps_to_504(monkeypatch):
    def fake(req, timeout):
        raise urllib.error.URLError("timed out")

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError) as ei:
        client.place_details("ChIJx")
    assert ei.value.status == 504


def test_resolve_maps_url_returns_place_id(monkeypatch):
    def fake(req, timeout):
        assert req.full_url == "https://mapstools.googleapis.com/v1:resolveMapsUrls"
        assert json.loads(req.data)["urls"] == ["https://maps.app.goo.gl/abc"]
        return _Resp(json.dumps({"entities": [{"placeId": "places/ChIJabc"}]}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.resolve_maps_url("https://maps.app.goo.gl/abc") == "ChIJabc"


def test_resolve_maps_url_unresolved_returns_none(monkeypatch):
    def fake(req, timeout):
        return _Resp(json.dumps({"entities": [{}], "failedRequests": {"0": {"code": 3}}}).encode())

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.resolve_maps_url("https://maps.app.goo.gl/dead") is None


def test_text_search_maps_candidates(monkeypatch):
    def fake(req, timeout):
        body = json.loads(req.data)
        assert body["textQuery"] == "Samir Kapsalon Lelystad"
        assert body["pageSize"] == 5
        assert body["locationBias"]["circle"]["center"] == {"latitude": 52.5, "longitude": 5.47}
        return _Resp(
            json.dumps(
                {
                    "places": [
                        {
                            "id": "ChIJ1",
                            "displayName": {"text": "Samir Kapsalon"},
                            "formattedAddress": "Stadhuisplein 1",
                        },
                        {"id": "ChIJ2", "displayName": {"text": "Samir Barber"}},
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr(client, "_urlopen", fake)
    out = client.text_search("Samir Kapsalon Lelystad", lat=52.5, lng=5.47)
    assert out == [
        {"place_id": "ChIJ1", "name": "Samir Kapsalon", "address": "Stadhuisplein 1"},
        {"place_id": "ChIJ2", "name": "Samir Barber", "address": None},
    ]


def test_photo_uri(monkeypatch):
    def fake(req, timeout):
        assert req.full_url == (
            "https://places.googleapis.com/v1/places/ChIJx/photos/abc/media"
            "?maxWidthPx=1600&skipHttpRedirect=true"
        )
        return _Resp(
            json.dumps(
                {
                    "name": "places/ChIJx/photos/abc",
                    "photoUri": "https://lh3.googleusercontent.com/p/x",
                }
            ).encode()
        )

    monkeypatch.setattr(client, "_urlopen", fake)
    assert client.photo_uri("places/ChIJx/photos/abc") == "https://lh3.googleusercontent.com/p/x"


def test_fetch_bytes_default_timeout_is_10s(monkeypatch):
    seen = {}

    def fake(req, timeout):
        seen["timeout"] = timeout
        return _Resp(b"x", headers={"Content-Type": "image/jpeg"})

    monkeypatch.setattr(client, "_urlopen", fake)
    client.fetch_bytes("https://lh3.googleusercontent.com/p/x")
    assert seen["timeout"] == 10


def test_fetch_bytes_caps_size_and_returns_type(monkeypatch):
    def fake(req, timeout):
        return _Resp(b"x" * 10, headers={"Content-Type": "image/jpeg"})

    monkeypatch.setattr(client, "_urlopen", fake)
    with pytest.raises(client.GooglePlacesError):
        client.fetch_bytes("https://lh3.googleusercontent.com/p/x", max_bytes=5)
    body, ctype = client.fetch_bytes("https://lh3.googleusercontent.com/p/x", max_bytes=20)
    assert body == b"x" * 10 and ctype == "image/jpeg"
