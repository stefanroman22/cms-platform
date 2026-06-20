# agents/SEO-GEO Optimizer/render_check.py
"""Fetch a page's RAW server HTML (the view AI/Google bots get — they don't run JS)
and extract deterministic on-page SEO/GEO signals. Stdlib only.
"""

from __future__ import annotations

import json
import re
import urllib.request
from html.parser import HTMLParser

# A GPTBot-style UA so we measure exactly what AI crawlers see.
_UA = "Mozilla/5.0 (compatible; SEOGEOAuditBot/1.0; +https://roman-technologies.dev)"
_BYTE_CAP = 600_000


def fetch_raw(url: str, timeout: int = 20) -> str:
    """GET the raw HTML (no JS execution). Raises urllib errors to the caller."""
    req = urllib.request.Request(url, headers={"User-Agent": _UA, "Accept": "text/html"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted client URLs)
        raw = resp.read(_BYTE_CAP)
    return raw.decode("utf-8", errors="replace")


class _TextHeadingParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[int] = []
        self.text_parts: list[str] = []
        self.links: list[str] = []
        self._skip = 0  # inside script/style

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("h1", "h2", "h3", "h4", "h5", "h6"):
            self.headings.append(int(tag[1]))
        if tag == "a":
            for k, v in attrs:
                if k == "href" and v:
                    self.links.append(v)

    def handle_endtag(self, tag: str) -> None:
        if tag in ("script", "style") and self._skip:
            self._skip -= 1

    def handle_data(self, data: str) -> None:
        if not self._skip and data.strip():
            self.text_parts.append(data.strip())


def _meta(html: str, attr: str, key: str) -> str | None:
    m = re.search(
        rf'<meta[^>]+{attr}=["\']{re.escape(key)}["\'][^>]*content=["\']([^"\']*)["\']',
        html,
        re.IGNORECASE,
    )
    if m:
        return m.group(1)
    m = re.search(
        rf'<meta[^>]+content=["\']([^"\']*)["\'][^>]*{attr}=["\']{re.escape(key)}["\']',
        html,
        re.IGNORECASE,
    )
    return m.group(1) if m else None


def _title(html: str) -> str | None:
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _canonical(html: str) -> str | None:
    m = re.search(
        r'<link[^>]+rel=["\']canonical["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE
    )
    return m.group(1) if m else None


def _jsonld(html: str) -> tuple[list[str], bool]:
    blocks = re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    )
    types: list[str] = []
    valid = True
    for b in blocks:
        try:
            data = json.loads(b.strip())
        except (ValueError, TypeError):
            valid = False
            continue
        queue = list(data) if isinstance(data, list) else [data]
        while queue:
            node = queue.pop()
            if not isinstance(node, dict):
                continue
            graph = node.get("@graph")
            if isinstance(graph, list):  # Yoast/RankMath/next-seo wrap nodes in @graph
                queue.extend(graph)
            t = node.get("@type")
            if isinstance(t, str):
                types.append(t)
            elif isinstance(t, list):
                types.extend(x for x in t if isinstance(x, str))
    return types, (valid if blocks else True)


_LOCAL_TYPES = {
    "LocalBusiness",
    "Restaurant",
    "Store",
    "HairSalon",
    "BeautySalon",
    "ProfessionalService",
    "Dentist",
    "MedicalBusiness",
    "FoodEstablishment",
}


def _headings_ordered(levels: list[int]) -> bool:
    """No skipped level on the way DOWN (e.g. h1 then h4 is a skip)."""
    prev = 0
    for lv in levels:
        if prev and lv > prev + 1:
            return False
        prev = lv
    return True


def extract_signals(html: str) -> dict:
    """Pure: HTML string -> deterministic signal dict (no network)."""
    p = _TextHeadingParser()
    p.feed(html)
    text = " ".join(p.text_parts)
    word_count = len(text.split())
    title = _title(html)
    desc = _meta(html, "name", "description")
    jsonld_types, jsonld_valid = _jsonld(html)
    internal = [
        h
        for h in p.links
        if h.startswith("/") or (not h.startswith(("http", "mailto:", "tel:", "#")))
    ]
    return {
        "h1_count": p.headings.count(1),
        "heading_order_ok": _headings_ordered(p.headings),
        "title": title,
        "title_len": len(title) if title else 0,
        "meta_description": desc,
        "meta_desc_len": len(desc) if desc else 0,
        "canonical": _canonical(html),
        "jsonld_types": jsonld_types,
        "jsonld_valid": jsonld_valid,
        "has_localbusiness": any(t in _LOCAL_TYPES for t in jsonld_types),
        "og_present": bool(
            _meta(html, "property", "og:title") or _meta(html, "property", "og:image")
        ),
        "internal_link_count": len(internal),
        "word_count": word_count,
        "has_main_content": word_count >= 50,
    }
