"""Tests for rich-text field formats (ADR-0010) in scan.py provisioning.

Covers:
  1. Repeater `inline`/`richtext` item_schema types reach the create payload and the seed.
  2. key_value `formats` reach the create payload and are seeded as `_formats`
     (default and non-default locale), with HTML values passed through untouched.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

import scan


def _urlopen_resp():
    m = MagicMock()
    m.read.return_value = b"{}"
    m.__enter__ = lambda s: s
    m.__exit__ = lambda s, *a: None
    return m


def _run(manifest):
    calls: list[tuple[str, str, dict]] = []

    def fake_urlopen(req):
        calls.append((req.get_method(), req.get_full_url(), json.loads(req.data or b"{}")))
        return _urlopen_resp()

    with (
        patch("urllib.request.urlopen", side_effect=fake_urlopen),
        patch.object(scan, "_http", return_value={"updated": 1}),
    ):
        scan._provision(manifest, "http://localhost:8001", "tok")
    return calls


_SCHEMA = [
    {"key": "name", "label": "Name", "type": "inline"},
    {"key": "bio", "label": "Bio", "type": "richtext"},
    {"key": "photo", "label": "Photo", "type": "url"},
]


def test_repeater_inline_richtext_types_in_create_and_seed():
    manifest = {
        "project_slug": "demo",
        "locales": ["en"],
        "default_locale": "en",
        "services": [
            {
                "service_type_slug": "repeater",
                "service_key": "team",
                "label": "Team",
                "item_schema": _SCHEMA,
                "initial_content": {
                    "items": [{"name": "A <em>B</em>", "bio": "<p>Hi <strong>x</strong></p>"}]
                },
            }
        ],
    }
    calls = _run(manifest)
    post = next(c for c in calls if c[0] == "POST")
    assert [f["type"] for f in post[2]["item_schema"]] == ["inline", "richtext", "url"]
    put = next(c for c in calls if c[0] == "PUT")
    assert put[2]["content"]["_schema"] == _SCHEMA
    assert put[2]["content"]["items"][0]["bio"] == "<p>Hi <strong>x</strong></p>"


def test_key_value_formats_in_create_and_seed_payloads():
    formats = {"tagline": "inline", "intro": "rich"}
    manifest = {
        "project_slug": "demo",
        "locales": ["en", "nl"],
        "default_locale": "en",
        "services": [
            {
                "service_type_slug": "key_value",
                "service_key": "copy",
                "label": "Copy",
                "formats": formats,
                "initial_content": {
                    "en": {"entries": {"tagline": "Hi <strong>you</strong>", "phone": "123"}},
                    "nl": {"entries": {"tagline": "Hoi <strong>jij</strong>", "phone": "123"}},
                },
            }
        ],
    }
    calls = _run(manifest)
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["formats"] == formats
    puts = [c for c in calls if c[0] == "PUT"]
    assert len(puts) == 2
    for _, _, body in puts:
        assert body["content"]["_formats"] == formats
    assert puts[0][2]["content"]["entries"]["tagline"] == "Hi <strong>you</strong>"


def test_key_value_without_formats_is_unchanged():
    svc = {"service_type_slug": "key_value", "service_key": "k"}
    content = {"entries": {"a": "b"}}
    assert scan._key_value_seed_content(svc, content) == content
    assert (
        scan._key_value_seed_content(
            {"service_type_slug": "text_block", "formats": {"a": "rich"}}, content
        )
        == content
    )
