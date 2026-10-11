from unittest.mock import MagicMock

from auth_service.services.google_places import client, photos

PUBLIC = "https://x.supabase.co/storage/v1/object/public/lead-photos/"


def _photo(n, author="Samir Kapsalon"):
    return {
        "name": f"places/P/photos/{n}",
        "width_px": 100,
        "height_px": 100,
        "attributions": [{"name": author, "uri": None, "photo_uri": None}],
        "google_maps_uri": f"https://g/{n}",
    }


def _sb():
    sb = MagicMock()
    store = sb.storage.from_.return_value
    store.get_public_url.side_effect = lambda path: PUBLIC + path
    return sb, store


def test_is_owner_photo():
    assert photos.is_owner_photo("Samir  Kapsalon", [{"name": "samir kapsalon"}])
    assert not photos.is_owner_photo("Samir Kapsalon", [{"name": "Jan"}])
    assert not photos.is_owner_photo("Samir Kapsalon", [])


def test_storage_path_of():
    assert photos.storage_path_of(PUBLIC + "lead-1/00-abc.jpg") == "lead-1/00-abc.jpg"
    assert photos.storage_path_of(PUBLIC + "lead-1/00-abc.jpg?v=1") == "lead-1/00-abc.jpg"
    assert (
        photos.storage_path_of("https://x.supabase.co/storage/v1/object/public/cms-files/a.jpg")
        is None
    )


def test_storage_path_of_rejects_traversal():
    assert photos.storage_path_of(PUBLIC + "lead-1/../lead-2/x.jpg") is None
    assert photos.storage_path_of(PUBLIC + "lead-1%2F..%2Flead-2%2Fx.jpg") is None
    assert photos.storage_path_of(PUBLIC + "lead-1//x.jpg") is None


def test_download_photos_uploads_and_flags_owner(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(
        client, "photo_uri", lambda name, max_width_px=1600: f"https://lh3/{name[-2:]}"
    )
    monkeypatch.setattr(
        client,
        "fetch_bytes",
        lambda url, max_bytes=8_000_000, timeout=15: (b"JPEGDATA" + url.encode(), "image/jpeg"),
    )
    urls, meta, warnings = photos.download_photos(
        sb, "lead-1", "Samir Kapsalon", [_photo("p1"), _photo("p2", author="Jan")], max_photos=10
    )
    assert warnings == []
    assert len(urls) == 2 and all(u.startswith(PUBLIC + "lead-1/") for u in urls)
    assert urls[0].endswith(".jpg") and urls[0].split("/")[-1].startswith("00-")
    assert meta[0]["owner_photo"] is True and meta[1]["owner_photo"] is False
    assert meta[0]["url"] == urls[0] and meta[0]["storage_path"].startswith("lead-1/00-")
    assert store.upload.call_count == 2
    kwargs = store.upload.call_args_list[0].kwargs
    assert kwargs["file_options"]["content-type"] == "image/jpeg"


def test_download_photos_respects_max(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: "https://lh3/x")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"PNG", "image/png"))
    urls, meta, _ = photos.download_photos(
        sb, "l", "B", [_photo(str(i)) for i in range(5)], max_photos=2
    )
    assert len(urls) == 2 and urls[0].endswith(".png")


def test_download_photos_continues_after_failure(monkeypatch):
    sb, store = _sb()

    def uri(name, max_width_px=1600):
        if name.endswith("p2"):
            raise client.GooglePlacesError(404, "expired")
        return "https://lh3/ok"

    monkeypatch.setattr(client, "photo_uri", uri)
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"JPG", "image/jpeg"))
    urls, meta, warnings = photos.download_photos(
        sb, "l", "B", [_photo("p1"), _photo("p2"), _photo("p3")], max_photos=10
    )
    assert len(urls) == 2 and len(set(urls)) == 2 and len(meta) == 2
    assert len(warnings) == 1 and "p2" in warnings[0]


def test_download_photos_skips_unknown_content_type(monkeypatch):
    sb, store = _sb()
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: "https://lh3/x")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (b"<html>", "text/html"))
    urls, meta, warnings = photos.download_photos(sb, "l", "B", [_photo("p1")], max_photos=10)
    assert urls == [] and len(warnings) == 1 and store.upload.call_count == 0


def test_delete_lead_photos_specific_urls():
    sb, store = _sb()
    removed = photos.delete_lead_photos(
        sb, "lead-1", [PUBLIC + "lead-1/00-a.jpg", "https://elsewhere/x.jpg"]
    )
    assert removed == ["lead-1/00-a.jpg"]
    store.remove.assert_called_once_with(["lead-1/00-a.jpg"])


def test_delete_lead_photos_ignores_other_lead_traversal():
    sb, store = _sb()
    removed = photos.delete_lead_photos(sb, "lead-1", [PUBLIC + "lead-1/../lead-2/x.jpg"])
    assert removed == []
    store.remove.assert_not_called()


def test_download_photos_survives_public_url_failure(monkeypatch):
    sb, store = _sb()

    calls = {"n": 0}

    def public_url(path):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("boom")
        return PUBLIC + path

    store.get_public_url.side_effect = public_url
    monkeypatch.setattr(client, "photo_uri", lambda name, max_width_px=1600: f"https://lh3/{name}")
    monkeypatch.setattr(client, "fetch_bytes", lambda url, **k: (url.encode(), "image/jpeg"))
    urls, meta, warnings = photos.download_photos(
        sb, "lead-1", "B", [_photo("p1"), _photo("p2"), _photo("p3")], max_photos=10
    )
    assert len(urls) == 2 and len(meta) == 2
    assert len(warnings) == 1 and "p1" in warnings[0]
    assert all(u.startswith(PUBLIC + "lead-1/") for u in urls)


def test_delete_lead_photos_all_under_prefix():
    sb, store = _sb()
    store.list.return_value = [{"name": "00-a.jpg", "id": "1"}, {"name": "01-b.jpg", "id": "2"}]
    removed = photos.delete_lead_photos(sb, "lead-1")
    assert removed == ["lead-1/00-a.jpg", "lead-1/01-b.jpg"]
    store.list.assert_called_once_with("lead-1", {"limit": 1000})
