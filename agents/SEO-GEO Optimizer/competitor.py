# agents/SEO-GEO Optimizer/competitor.py
"""Extract structured signals from a competitor's RAW HTML and compute advisory content
gaps vs the client. Free-tools only (no paid SEO APIs). Stdlib only.

The output FEEDS the LLM competitor analyst (prompts.COMPETITOR_ANALYST_PROMPT) for the
reasoned write-up; this module only produces the deterministic substrate. No refuted stats.
"""

from __future__ import annotations

import json
import re
from html.parser import HTMLParser


class _Collect(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.headings: list[str] = []
        self._in_h = 0
        self._buf: list[str] = []
        self.text_words = 0
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style"):
            self._skip += 1
        if tag in ("h1", "h2", "h3"):
            self._in_h += 1
            self._buf = []

    def handle_endtag(self, tag):
        if tag in ("script", "style") and self._skip:
            self._skip -= 1
        if tag in ("h1", "h2", "h3") and self._in_h:
            self._in_h -= 1
            h = " ".join(self._buf).strip()
            if h:
                self.headings.append(h)

    def handle_data(self, data):
        if self._skip:
            return
        if self._in_h:
            self._buf.append(data.strip())
        if data.strip():
            self.text_words += len(data.split())


def _jsonld_types(html: str) -> list[str]:
    out: list[str] = []
    for b in re.findall(
        r'<script[^>]+type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
        html,
        re.IGNORECASE | re.DOTALL,
    ):
        try:
            data = json.loads(b.strip())
        except (ValueError, TypeError):
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
                out.append(t)
            elif isinstance(t, list):
                out.extend(x for x in t if isinstance(x, str))
    return out


def extract_competitor_signals(html: str) -> dict:
    p = _Collect()
    p.feed(html)
    types = _jsonld_types(html)
    has_faq = ("FAQPage" in types) or bool(
        re.search(r"\b(faq|frequently asked|veelgestelde vragen)\b", html, re.IGNORECASE)
    )
    return {
        "jsonld_types": types,
        "headings": p.headings,
        "word_count": p.text_words,
        "has_faq": has_faq,
    }


def content_gaps(client: dict, competitors: list[dict]) -> list[str]:
    """Advisory, plain-language gaps. No refuted stats, no fabricated numbers."""
    gaps: list[str] = []
    if not competitors:
        return gaps
    avg_words = sum(c.get("word_count", 0) for c in competitors) / len(competitors)
    client_words = client.get("word_count", 0)
    if avg_words > max(1, client_words) * 1.5 and avg_words - client_words > 150:
        gaps.append(
            f"Competitors have far more page depth (~{int(avg_words)} words avg vs your "
            f"{client_words}). Thin content limits both Google and AI-answer coverage."
        )
    if any(c.get("has_faq") for c in competitors) and not client.get("has_faq"):
        gaps.append(
            "Competitors use FAQ-structured Q&A content (short, citable passages) and you do not - "
            "add genuine Q&A where it fits."
        )
    client_h = {h.lower() for h in client.get("headings", [])}
    rival_topics: dict[str, int] = {}
    for c in competitors:
        for h in c.get("headings", []):
            key = h.lower().strip()
            if key and key not in client_h and len(key) < 60:
                rival_topics[key] = rival_topics.get(key, 0) + 1
    common = [
        t
        for t, n in sorted(rival_topics.items(), key=lambda kv: -kv[1])
        if n >= max(1, len(competitors) // 2)
    ]
    if common:
        gaps.append("Topics competitors cover that you do not: " + ", ".join(common[:8]) + ".")
    return gaps
