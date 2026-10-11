"""Pull social links, an email and a meta description out of the business's own
website (ADR-0012). Places API never exposes social profiles, so this is the only
source. Fetch is SSRF-guarded (public IPs only, redirects re-checked), capped at 1 MB
and 8 s, and every failure is reported, never raised, from enrich_from_website()."""

from __future__ import annotations

import ipaddress
import json
import re
import socket
import urllib.parse
import urllib.request
from html.parser import HTMLParser

USER_AGENT = "roman-technologies-cms-backend/1.0"

SOCIAL_HOSTS: dict[str, tuple[str, ...]] = {
    "facebook": ("facebook.com", "fb.com", "fb.me"),
    "instagram": ("instagram.com",),
    "tiktok": ("tiktok.com",),
    "linkedin": ("linkedin.com",),
    "youtube": ("youtube.com",),
    "x": ("x.com", "twitter.com"),
    "pinterest": ("pinterest.com",),
    "whatsapp": ("wa.me", "api.whatsapp.com", "chat.whatsapp.com"),
}
# Path segments that mean "share/post/intent", not a profile. Matched as whole segments.
_NOT_PROFILE_SEGMENTS: dict[str, frozenset[str]] = {
    "facebook": frozenset(
        {
            "sharer",
            "sharer.php",
            "share",
            "share.php",
            "dialog",
            "plugins",
            "login",
            "photo",
            "photo.php",
            "photos",
            "posts",
            "videos",
            "watch",
            "reel",
            "reels",
            "stories",
            "events",
            "hashtag",
        }
    ),
    "instagram": frozenset({"p", "reel", "reels", "explore", "accounts", "stories", "tv"}),
    "tiktok": frozenset({"video", "tag", "discover", "music"}),
    "linkedin": frozenset({"share", "sharearticle", "feed", "posts", "pulse"}),
    "youtube": frozenset({"watch", "embed", "shorts", "playlist", "results", "feed"}),
    "x": frozenset({"intent", "share", "status", "hashtag", "search", "home", "i"}),
    "pinterest": frozenset({"pin", "search", "ideas"}),
    "whatsapp": frozenset(),
}


def _host_of(url: str) -> tuple[urllib.parse.SplitResult | None, str]:
    try:
        p = urllib.parse.urlsplit(url.strip())
    except ValueError:
        return None, ""
    if p.scheme not in ("http", "https") or not p.hostname:
        return None, ""
    host = p.hostname.lower()
    for prefix in ("www.", "m.", "mobile."):
        host = host.removeprefix(prefix)
    return p, host


def _platform_for_host(host: str) -> str | None:
    for platform, hosts in SOCIAL_HOSTS.items():
        for h in hosts:
            # 'nl.linkedin.com', 'nl.pinterest.com', 'pinterest.nl' style variants
            if (
                host == h
                or host.endswith("." + h)
                or (platform == "pinterest" and _PINTEREST_CC.fullmatch(host))
            ):
                return platform
    return None


_PINTEREST_CC = re.compile(r"pinterest\.(?:com|[a-z]{2}|co\.[a-z]{2}|com\.[a-z]{2})")


def social_platform_of(url: str) -> str | None:
    """Platform key when `url` is a profile/page link on a known social host, else None."""
    p, host = _host_of(url)
    if p is None:
        return None
    platform = _platform_for_host(host)
    if platform is None:
        return None
    path = p.path.lower()
    segments = path.strip("/").split("/")
    if any(seg in _NOT_PROFILE_SEGMENTS[platform] for seg in segments):
        return None
    if platform != "whatsapp" and path.strip("/") == "":
        return None  # bare homepage link, not the business's page
    return platform


def normalize_social_url(platform: str, url: str) -> str:
    p = urllib.parse.urlsplit(url.strip())
    netloc = (p.hostname or "").lower()
    path = p.path.rstrip("/")
    if platform == "whatsapp" and netloc in ("api.whatsapp.com", "chat.whatsapp.com"):
        q = urllib.parse.parse_qs(p.query)
        phone = (q.get("phone") or [""])[0]
        if phone:
            return f"https://wa.me/{phone.lstrip('+')}"
    if platform == "facebook" and path.lower().strip("/") == "profile.php":
        # numeric-id profiles: the id is the page, so keep it (and only it)
        fb_id = (urllib.parse.parse_qs(p.query).get("id") or [""])[0]
        if fb_id:
            return f"https://{netloc}{path}?id={urllib.parse.quote(fb_id, safe='')}"
    return f"https://{netloc}{path}"


class UnsafeUrl(ValueError):
    pass


def assert_public_http_url(url: str) -> None:
    p, _ = _host_of(url)
    if p is None:
        raise UnsafeUrl("only http(s) URLs with a host are allowed")
    port = p.port or (443 if p.scheme == "https" else 80)
    try:
        infos = socket.getaddrinfo(p.hostname, port, proto=socket.IPPROTO_TCP)
    except socket.gaierror as e:
        raise UnsafeUrl(f"cannot resolve {p.hostname}") from e
    if not infos:
        raise UnsafeUrl(f"cannot resolve {p.hostname}")
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            not ip.is_global
            or ip.is_private
            or ip.is_loopback
            or ip.is_link_local
            or ip.is_reserved
            or ip.is_multicast
            or ip.is_unspecified
        ):
            raise UnsafeUrl(f"{p.hostname} resolves to a non-public address")


class _SafeRedirects(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        assert_public_http_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


def _open(url: str, timeout: int):
    """Single seam for tests."""
    opener = urllib.request.build_opener(_SafeRedirects())
    req = urllib.request.Request(
        url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,*/*;q=0.5"}
    )
    return opener.open(req, timeout=timeout)


def fetch_html(url: str, *, timeout: int = 8, max_bytes: int = 1_000_000) -> tuple[str, str]:
    assert_public_http_url(url)
    with _open(url, timeout) as resp:
        ctype = (resp.headers.get("Content-Type") or "").lower()
        if "html" not in ctype:
            raise ValueError(f"not HTML ({ctype.split(';')[0] or 'no content-type'})")
        raw = resp.read(max_bytes)
        final = resp.geturl() or url
        charset = resp.headers.get_content_charset() or "utf-8"
    try:
        return final, raw.decode(charset, errors="replace")
    except LookupError:
        return final, raw.decode("utf-8", errors="replace")


class _Collector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.hrefs: list[str] = []
        self.meta: dict[str, str] = {}
        self.lang: str | None = None
        self.jsonld: list[str] = []
        self._in_jsonld = False

    def handle_starttag(self, tag, attrs):
        a = {k: (v or "") for k, v in attrs}
        if tag == "a" and a.get("href"):
            self.hrefs.append(a["href"].strip())
        elif tag == "meta":
            key = (a.get("name") or a.get("property") or "").lower()
            if key in ("description", "og:description") and a.get("content", "").strip():
                self.meta.setdefault(key, a["content"].strip())
        elif tag == "html" and a.get("lang"):
            self.lang = a["lang"].strip()[:10] or None
        elif tag == "script" and (a.get("type") or "").lower() == "application/ld+json":
            self._in_jsonld = True

    def handle_endtag(self, tag):
        if tag == "script":
            self._in_jsonld = False

    def handle_data(self, data):
        if self._in_jsonld:
            self.jsonld.append(data)


def _same_as(blobs: list[str]) -> list[str]:
    found: list[str] = []

    def walk(node):
        if isinstance(node, dict):
            same = node.get("sameAs")
            if isinstance(same, str):
                found.append(same)
            elif isinstance(same, list):
                found.extend(s for s in same if isinstance(s, str))
            for v in node.values():
                walk(v)
        elif isinstance(node, list):
            for v in node:
                walk(v)

    for blob in blobs:
        try:
            walk(json.loads(blob))
        except ValueError:
            continue
    return found


def extract(html: str) -> dict:
    c = _Collector()
    c.feed(html)
    social: dict[str, str] = {}
    email: str | None = None
    for href in c.hrefs + _same_as(c.jsonld):
        if href.lower().startswith("mailto:"):
            if email is None:
                addr = href[7:].split("?", 1)[0].strip()
                if "@" in addr:
                    email = addr
            continue
        platform = social_platform_of(href)
        if platform and platform not in social:
            social[platform] = normalize_social_url(platform, href)
    description = c.meta.get("description") or c.meta.get("og:description")
    return {"social_links": social, "email": email, "description": description, "lang": c.lang}


def enrich_from_website(url: str) -> dict:
    out = {
        "fetched": False,
        "final_url": None,
        "social_links": {},
        "email": None,
        "description": None,
        "lang": None,
        "error": None,
    }
    try:
        final, html = fetch_html(url)
        out.update(extract(html))
    except Exception as e:  # noqa: BLE001 — any failure is a warning, never an import failure
        out["error"] = f"{type(e).__name__}: {e}"[:300]
        return out
    out["fetched"] = True
    out["final_url"] = final
    return out
