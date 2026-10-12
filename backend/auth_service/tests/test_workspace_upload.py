"""Tests for POST /projects/{slug}/services/{key}/upload (SVG sanitising, theme fonts)."""

from io import BytesIO
from unittest.mock import MagicMock

import pytest

URL = "/projects/acme/services/svc/upload"


@pytest.fixture
def upload_env(mock_supabase, auth_as, client_user):
    """Authenticated client user; returns a setter for the service's type."""
    auth_as(client_user)
    storage = mock_supabase.storage.from_.return_value
    storage.get_public_url.return_value = "https://cdn.example.com/acme/svc/file"

    def _set_type(service_type: str) -> MagicMock:
        mock_supabase.execute.return_value = MagicMock(data={"service_type_slug": service_type})
        return storage

    return _set_type


def _post(client, name: str, data: bytes, mime: str):
    return client.post(URL, files={"file": (name, BytesIO(data), mime)})


def _uploaded(storage: MagicMock) -> tuple[str, bytes, dict]:
    kwargs = storage.upload.call_args.kwargs
    return kwargs["path"], kwargs["file"], kwargs["file_options"]


def test_repeater_accepts_png(client, upload_env):
    storage = upload_env("repeater")
    r = _post(client, "a.png", b"PNG", "image/png")
    assert r.status_code == 200
    path, _, opts = _uploaded(storage)
    assert path.startswith("acme/svc/") and path.endswith(".png")
    assert opts["content-type"] == "image/png"


def test_repeater_svg_is_sanitised(client, upload_env):
    storage = upload_env("repeater")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>alert(1)</script><path d="M0 0"/></svg>'
    r = _post(client, "icon.svg", svg, "image/svg+xml")
    assert r.status_code == 200
    path, body, opts = _uploaded(storage)
    assert b"script" not in body
    assert b'<path d="M0 0" />' in body
    assert path.endswith(".svg")
    assert opts["content-type"] == "image/svg+xml"
    assert r.json()["mime_type"] == "image/svg+xml"
    assert r.json()["size"] == len(body)


def test_image_service_svg_is_sanitised(client, upload_env):
    storage = upload_env("image")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg" onload="alert(1)"><rect width="1"/></svg>'
    r = _post(client, "pic.svg", svg, "image/svg+xml")
    assert r.status_code == 200
    _, body, opts = _uploaded(storage)
    assert b"onload" not in body
    assert b'<rect width="1" />' in body
    assert opts["content-type"] == "image/svg+xml"


def test_svg_by_extension_with_generic_mime_is_sanitised(client, upload_env):
    storage = upload_env("image")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>'
    r = _post(client, "pic.svg", svg, "application/octet-stream")
    assert r.status_code == 200
    _, body, opts = _uploaded(storage)
    assert b"script" not in body
    assert opts["content-type"] == "image/svg+xml"


def test_svg_with_other_extension_is_stored_as_svg(client, upload_env):
    storage = upload_env("image")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><g/></svg>'
    r = _post(client, "pic.png", svg, "image/svg+xml")
    assert r.status_code == 200
    path, _, _ = _uploaded(storage)
    assert path.endswith(".svg")


def test_svg_mime_with_params_is_sanitised(client, upload_env):
    storage = upload_env("image")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"><script>x</script></svg>'
    r = _post(client, "pic.png", svg, "IMAGE/SVG+XML; charset=utf-8")
    assert r.status_code == 200
    path, body, opts = _uploaded(storage)
    assert b"script" not in body
    assert path.endswith(".svg")
    assert opts["content-type"] == "image/svg+xml"


def test_malformed_svg_rejected(client, upload_env):
    storage = upload_env("image")
    r = _post(client, "bad.svg", b"<svg><path></svg>", "image/svg+xml")
    assert r.status_code == 422
    assert r.json()["detail"].startswith("SVG rejected: ")
    storage.upload.assert_not_called()


def test_deeply_nested_svg_rejected(client, upload_env):
    storage = upload_env("image")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg">' + b"<g>" * 5000 + b"</g>" * 5000 + b"</svg>"
    r = _post(client, "deep.svg", svg, "image/svg+xml")
    assert r.status_code == 422
    assert r.json()["detail"].startswith("SVG rejected: ")
    storage.upload.assert_not_called()


def test_svg_still_refused_for_video_service(client, upload_env):
    storage = upload_env("video")
    svg = b'<svg xmlns="http://www.w3.org/2000/svg"/>'
    r = _post(client, "clip.svg", svg, "application/octet-stream")
    assert r.status_code == 422
    storage.upload.assert_not_called()


def test_theme_accepts_woff2_by_extension(client, upload_env):
    storage = upload_env("theme")
    r = _post(client, "x.woff2", b"wOF2data", "application/octet-stream")
    assert r.status_code == 200
    path, body, opts = _uploaded(storage)
    assert opts["content-type"] == "font/woff2"
    assert path.endswith(".woff2")
    assert body == b"wOF2data"
    assert r.json()["mime_type"] == "font/woff2"


@pytest.mark.parametrize(
    ("name", "mime"),
    [("x.woff", "font/woff"), ("x.ttf", "font/ttf"), ("x.otf", "font/otf")],
)
def test_theme_font_mime_from_extension(client, upload_env, name, mime):
    storage = upload_env("theme")
    r = _post(client, name, b"font", "text/plain")
    assert r.status_code == 200
    assert _uploaded(storage)[2]["content-type"] == mime


def test_theme_rejects_png(client, upload_env):
    storage = upload_env("theme")
    r = _post(client, "x.png", b"PNG", "image/png")
    assert r.status_code == 422
    assert r.json()["detail"] == "Theme uploads accept font files (.woff2, .woff, .ttf, .otf)"
    storage.upload.assert_not_called()


def test_theme_rejects_svg(client, upload_env):
    storage = upload_env("theme")
    r = _post(client, "x.svg", b"<svg/>", "image/svg+xml")
    assert r.status_code == 422
    storage.upload.assert_not_called()


def test_theme_font_over_5mb_rejected(client, upload_env):
    storage = upload_env("theme")
    r = _post(client, "x.woff2", b"x" * (5 * 1024 * 1024 + 1), "font/woff2")
    assert r.status_code == 413
    storage.upload.assert_not_called()


def test_storage_rejection_is_422(client, upload_env):
    from storage3.exceptions import StorageApiError

    storage = upload_env("repeater")
    storage.upload.side_effect = StorageApiError(
        "mime type image/x-icon is not supported", "invalid_mime_type", 400
    )
    r = _post(client, "a.ico", b"ICO", "image/x-icon")
    assert r.status_code == 422
    assert r.json()["detail"] == (
        "Storage rejected this file type (mime type image/x-icon is not supported)"
    )


def test_html_still_denied(client, upload_env):
    storage = upload_env("file_download")
    r = _post(client, "x.html", b"<script></script>", "text/html")
    assert r.status_code == 422
    storage.upload.assert_not_called()
