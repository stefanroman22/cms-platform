import io
import socket
from pathlib import Path

import pytest

from auth_service.services.google_places import website_enrich as we

FIX = Path(__file__).parent / "fixtures" / "website_sample.html"


@pytest.mark.parametrize(
    "url,platform",
    [
        ("https://www.facebook.com/samirkapsalon/", "facebook"),
        ("https://m.facebook.com/samirkapsalon", "facebook"),
        ("https://www.facebook.com/sharer/sharer.php?u=x", None),
        ("https://www.facebook.com/", None),
        ("https://instagram.com/samir.kapsalon?igshid=abc", "instagram"),
        ("https://www.instagram.com/p/C123/", None),
        ("https://www.tiktok.com/@samir", "tiktok"),
        ("https://www.tiktok.com/@samir/video/123", None),
        ("https://nl.linkedin.com/company/samir", "linkedin"),
        ("https://www.linkedin.com/shareArticle?mini=true", None),
        ("https://www.youtube.com/@samir", "youtube"),
        ("https://www.youtube.com/watch?v=abc", None),
        ("https://x.com/samir", "x"),
        ("https://twitter.com/intent/tweet?text=x", None),
        ("https://nl.pinterest.com/samir/", "pinterest"),
        ("https://wa.me/31612345678", "whatsapp"),
        ("https://samirkapsalon.nl/", None),
        ("javascript:alert(1)", None),
        ("not a url", None),
        ("https://facebook.com/photographybyx", "facebook"),
        ("https://facebook.com/sharedspace", "facebook"),
        ("https://facebook.com/acme/posts/123", None),
        ("https://youtu.be/abc123", None),
        ("https://pinterest.attacker.example/x", None),
        ("https://pinterest.nl/samir", "pinterest"),
    ],
)
def test_social_platform_of(url, platform):
    assert we.social_platform_of(url) == platform


def test_extract_survives_deeply_nested_json_ld(monkeypatch):
    html = (
        '<html><head><script type="application/ld+json">' + "[" * 100000 + "</script></head></html>"
    )
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(html.encode()))
    out = we.enrich_from_website("https://samirkapsalon.nl/")
    assert out["fetched"] is False and out["error"]


def test_fetch_html_unknown_charset_falls_back_to_utf8(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    body = "<html>café</html>".encode()
    monkeypatch.setattr(
        we, "_open", lambda url, timeout: _Resp(body, ctype="text/html; charset=bogus-enc")
    )
    _, html = we.fetch_html("https://samirkapsalon.nl/")
    assert "café" in html


def test_normalize_social_url_strips_query_and_slash():
    assert (
        we.normalize_social_url("instagram", "http://instagram.com/samir.kapsalon/?igshid=abc")
        == "https://instagram.com/samir.kapsalon"
    )


def test_normalize_social_url_keeps_facebook_profile_id():
    assert (
        we.normalize_social_url(
            "facebook", "https://www.facebook.com/profile.php?id=100063512345678&ref=x"
        )
        == "https://www.facebook.com/profile.php?id=100063512345678"
    )


def test_normalize_social_url_keeps_whatsapp_phone():
    assert (
        we.normalize_social_url("whatsapp", "https://wa.me/31612345678?text=hi")
        == "https://wa.me/31612345678"
    )


def test_extract_from_fixture():
    out = we.extract(FIX.read_text(encoding="utf-8"))
    assert out["social_links"] == {
        "facebook": "https://www.facebook.com/samirkapsalon",
        "instagram": "https://instagram.com/samir.kapsalon",
        "whatsapp": "https://wa.me/31612345678",
        "x": "https://x.com/samirkapsalon",
        "linkedin": "https://nl.linkedin.com/company/samir-kapsalon",
        "pinterest": "https://nl.pinterest.com/samirkapsalon",
        "tiktok": "https://www.tiktok.com/@samirkapsalon",
        "youtube": "https://www.youtube.com/@samirkapsalon",
    }
    assert out["email"] == "info@samirkapsalon.nl"
    assert out["description"] == "Samir Kapsalon — moderne barbier in Lelystad."
    assert out["lang"] == "nl"


def test_extract_uses_og_description_when_no_meta_description():
    html = (
        '<html><head><meta property="og:description" content="Only OG"></head><body></body></html>'
    )
    assert we.extract(html)["description"] == "Only OG"


def test_extract_empty_page():
    assert we.extract("<html></html>") == {
        "social_links": {},
        "email": None,
        "description": None,
        "lang": None,
    }


def _addr(ip):
    return lambda host, port, **kw: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


def test_assert_public_rejects_private(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("10.0.0.5"))
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("https://intranet.example/")


def test_assert_public_rejects_loopback_and_scheme(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("127.0.0.1"))
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("http://localhost/")
    with pytest.raises(we.UnsafeUrl):
        we.assert_public_http_url("ftp://example.com/")


def test_assert_public_accepts_public(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    we.assert_public_http_url("https://example.com/")


class _Resp(io.BytesIO):
    def __init__(self, body, ctype="text/html; charset=utf-8", url="https://samirkapsalon.nl/"):
        super().__init__(body)
        self._ctype, self._url = ctype, url

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass

    def geturl(self):
        return self._url

    @property
    def headers(self):
        import email.message

        m = email.message.Message()
        m["Content-Type"] = self._ctype
        return m


def test_fetch_html_caps_bytes(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(b"<html>" + b"x" * 5000))
    final, html = we.fetch_html("https://samirkapsalon.nl/", max_bytes=100)
    assert final == "https://samirkapsalon.nl/" and len(html) == 100


def test_non_html_rejected(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(b"%PDF", ctype="application/pdf"))
    with pytest.raises(ValueError, match="not HTML"):
        we.fetch_html("https://samirkapsalon.nl/menu.pdf")


def test_redirect_to_private_ip_rejected(monkeypatch):
    """_SafeRedirects re-validates the Location target."""
    import urllib.request

    seen = []

    def getaddrinfo(host, port, **kw):
        seen.append(host)
        ip = "10.0.0.5" if host == "internal.local" else "93.184.216.34"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", getaddrinfo)
    handler = we._SafeRedirects()
    req = urllib.request.Request("https://samirkapsalon.nl/")
    with pytest.raises(we.UnsafeUrl):
        handler.redirect_request(req, None, 302, "Found", {}, "http://internal.local/admin")
    assert "internal.local" in seen


def test_fetch_html_connects_to_validated_ip_not_hostname(monkeypatch):
    """Pinning: the socket is opened against the resolved IP literal, never the hostname
    — so the kernel cannot perform a second, unvalidated DNS lookup at connect time."""
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    seen = []

    class _Stop(Exception):
        pass

    def fake_create_connection(address, *a, **k):
        seen.append(address)
        raise _Stop()

    monkeypatch.setattr(socket, "create_connection", fake_create_connection)
    with pytest.raises(_Stop):
        we.fetch_html("https://samirkapsalon.nl/")
    assert seen and seen[0] == ("93.184.216.34", 443)


def test_fetch_html_rebinding_rejected_at_connect(monkeypatch):
    """SEC-072 TOCTOU: getaddrinfo returns a public IP for the pre-check then a private
    IP at connect (DNS rebinding). The connect-time re-validation must refuse, and no
    socket may be opened to the unvalidated address."""
    calls = []

    def flipping(host, port, **kw):
        calls.append(host)
        ip = "93.184.216.34" if len(calls) == 1 else "10.0.0.5"
        return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]

    monkeypatch.setattr(socket, "getaddrinfo", flipping)
    connected = []
    monkeypatch.setattr(
        socket, "create_connection", lambda address, *a, **k: connected.append(address)
    )
    with pytest.raises(we.UnsafeUrl):
        we.fetch_html("https://rebind.example/")
    assert connected == []  # refused before any socket was opened
    assert len(calls) >= 2  # pre-check resolved, then connect re-resolved and caught the flip


def test_assert_public_rejects_nonweb_port(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    with pytest.raises(we.UnsafeUrl, match="port 22"):
        we.assert_public_http_url("https://example.com:22/")


def test_enrich_from_website_reports_error_instead_of_raising(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))

    def boom(url, timeout):
        raise OSError("connection refused")

    monkeypatch.setattr(we, "_open", boom)
    out = we.enrich_from_website("https://samirkapsalon.nl/")
    assert out["fetched"] is False and "connection refused" in out["error"]
    assert out["social_links"] == {} and out["email"] is None


def test_enrich_from_website_happy(monkeypatch):
    monkeypatch.setattr(socket, "getaddrinfo", _addr("93.184.216.34"))
    monkeypatch.setattr(we, "_open", lambda url, timeout: _Resp(FIX.read_bytes()))
    out = we.enrich_from_website("https://samirkapsalon.nl/")
    assert out["fetched"] is True and out["error"] is None
    assert out["social_links"]["tiktok"] == "https://www.tiktok.com/@samirkapsalon"
    assert out["final_url"] == "https://samirkapsalon.nl/"
