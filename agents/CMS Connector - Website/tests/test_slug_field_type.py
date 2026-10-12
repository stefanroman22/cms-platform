"""Per-item URL slugs use the repeater `slug` field type, never `string`.

A `string` slug is machine-translated as prose (EN `laptop repairs and maintenance`,
spaces and all); a `slug` field is translated as words and stored slugified.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import prompts
import scan

_ROOT = Path(__file__).resolve().parents[1]

_SCHEMA = [
    {"key": "title", "label": "Title", "type": "inline"},
    {"key": "slug", "label": "URL slug", "type": "slug"},
]


def test_prompt_lists_slug_type_and_forbids_string_slugs():
    p = prompts.SYSTEM_PROMPT
    assert "string|inline|richtext|url|tags|slug|image|icon" in p
    assert "URL slug field is type `slug`, never `string`" in p


def test_scan_phase_doc_requires_slug_type():
    doc = (_ROOT / "phases" / "2-scan.md").read_text(encoding="utf-8")
    assert "URL slug field is type `slug`, never `string`" in doc
    assert "`tags`, `slug`" in doc


def test_agents_md_lists_slug_type():
    doc = (_ROOT / "AGENTS.md").read_text(encoding="utf-8")
    assert "`tags`, `slug`" in doc


def _urlopen_resp():
    m = MagicMock()
    m.read.return_value = b"{}"
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


def test_slug_field_reaches_create_and_seed():
    calls: list[tuple[str, str, dict]] = []

    def fake_urlopen(req):
        calls.append((req.get_method(), req.get_full_url(), json.loads(req.data or b"{}")))
        return _urlopen_resp()

    manifest = {
        "project_slug": "demo",
        "locales": ["en"],
        "default_locale": "en",
        "services": [
            {
                "service_key": "services_catalog",
                "service_type_slug": "repeater",
                "label": "Services",
                "page_name": "Services",
                "item_schema": _SCHEMA,
                "initial_content": {
                    "items": [{"title": "Laptop repairs", "slug": "laptop-repairs"}]
                },
            }
        ],
    }
    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", return_value={"updated": 1}),
    ):
        scan._provision(manifest, "http://localhost:8001", "tok")
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["item_schema"] == _SCHEMA
    put = next(c for c in calls if c[0] == "PUT")
    assert put[2]["content"]["_schema"] == _SCHEMA
    assert put[2]["content"]["items"][0]["slug"] == "laptop-repairs"
