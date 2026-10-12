"""Tests for the theme service and image/icon field types (ADR-0011).

Covers:
  1. The Phase-2 SYSTEM_PROMPT asks for a `general_theme` service and for repeater
     `image`/`icon` fields with `hint`/`surface`.
  2. cms.config.json carries the `theme` service type through, and records repeater
     image/icon fields (with hint/surface) and an image service's `_hint`.
  3. Provisioning creates the theme service and seeds it once (default locale only),
     and image/icon schema fields keep `hint`/`surface` in the create and seed payloads.
"""

from __future__ import annotations

import json
import tempfile
from unittest.mock import MagicMock, patch

import output_writer
import prompts
import scan

_THEME = {
    "colors": [{"name": "Brand", "value": "#1e5aa8"}],
    "surfaces": [{"name": "Page light", "value": "#ffffff"}, {"name": "Card", "value": "#f4f6fa"}],
    "fonts": [{"family": "Open Sans", "source": "google", "weights": [400, 700], "italic": False}],
    "body_font": "Open Sans",
    "heading_font": "Open Sans",
}

_SCHEMA = [
    {"key": "title", "label": "Title", "type": "inline"},
    {"key": "banner", "label": "Banner", "type": "image", "hint": {"width": 1600, "height": 600}},
    {"key": "icon", "label": "Icon", "type": "icon", "surface": "Card"},
]


def _theme_svc() -> dict:
    return {
        "service_key": "general_theme",
        "service_type_slug": "theme",
        "label": "Theme",
        "page_name": "General",
        "translatable": False,
        "initial_content": _THEME,
    }


def _repeater_svc(initial_content: dict) -> dict:
    return {
        "service_key": "services_list",
        "service_type_slug": "repeater",
        "label": "Services",
        "page_name": "Services",
        "item_schema": _SCHEMA,
        "initial_content": initial_content,
    }


# ---------------------------------------------------------------------------
# 1. SYSTEM_PROMPT
# ---------------------------------------------------------------------------


def test_prompt_asks_for_general_theme_service():
    p = prompts.SYSTEM_PROMPT
    assert "general_theme" in p
    assert "| theme |" in p
    assert "body_font" in p and "heading_font" in p


def test_prompt_lists_image_and_icon_field_types_with_hint_and_surface():
    p = prompts.SYSTEM_PROMPT
    assert "string|inline|richtext|url|tags|image|icon" in p
    assert '"hint"' in p and '"surface"' in p
    assert "_hint" in p
    assert "<CmsIcon>" in p


def test_prompt_scopes_icon_fields_to_content_icons():
    p = prompts.SYSTEM_PROMPT
    assert "Every content icon is a CMS icon field" in p
    assert "UI-control icons" in p


def test_prompt_seeds_self_hosted_fonts_as_system_not_upload():
    p = prompts.SYSTEM_PROMPT
    assert 'non-Google font the site self-hosts, never `"upload"`' in p


# ---------------------------------------------------------------------------
# 2. cms.config.json
# ---------------------------------------------------------------------------


def _config(manifest: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        config_path, _ = output_writer.write_outputs(manifest, tmp)
        return json.loads(config_path.read_text(encoding="utf-8"))


def test_config_carries_theme_service_type():
    config = _config({"project_slug": "demo", "services": [_theme_svc()]})
    assert config["services"]["general_theme"] == {"type": "theme", "page": "General"}


def test_config_records_repeater_media_fields():
    config = _config({"project_slug": "demo", "services": [_repeater_svc({"items": []})]})
    assert config["services"]["services_list"] == {
        "type": "repeater",
        "page": "Services",
        "media": {
            "banner": {"type": "image", "hint": {"width": 1600, "height": 600}},
            "icon": {"type": "icon", "surface": "Card"},
        },
    }


def test_config_records_image_service_hint():
    svc = {
        "service_key": "home_hero_image",
        "service_type_slug": "image",
        "page_name": "Home",
        "translatable": False,
        "initial_content": {"url": "", "alt": "", "_hint": {"width": 1600, "height": 900}},
    }
    config = _config({"project_slug": "demo", "services": [svc]})
    assert config["services"]["home_hero_image"] == {
        "type": "image",
        "page": "Home",
        "hint": {"width": 1600, "height": 900},
    }


def test_config_without_media_is_unchanged():
    svc = {
        "service_key": "team",
        "service_type_slug": "repeater",
        "page_name": "About",
        "item_schema": [{"key": "name", "label": "Name", "type": "string"}],
    }
    config = _config({"project_slug": "demo", "services": [svc]})
    assert config["services"]["team"] == {"type": "repeater", "page": "About"}


# ---------------------------------------------------------------------------
# 3. Provisioning
# ---------------------------------------------------------------------------


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


def test_theme_service_created_and_seeded_once_in_default_locale():
    manifest = {
        "project_slug": "demo",
        "locales": ["en", "nl"],
        "default_locale": "en",
        "services": [_theme_svc()],
    }
    calls = _run(manifest)
    posts = [c for c in calls if c[0] == "POST"]
    assert len(posts) == 1
    assert posts[0][2]["service_type_slug"] == "theme"
    assert posts[0][2]["service_key"] == "general_theme"
    puts = [c for c in calls if c[0] == "PUT"]
    assert len(puts) == 1
    assert "locale=" not in puts[0][1]
    assert puts[0][2]["content"] == _THEME


def test_media_schema_hint_and_surface_reach_create_and_seed():
    item = {
        "title": "Cloud",
        "banner": "https://cdn.example.com/b.jpg",
        "icon": {
            "src": "https://cdn.example.com/i.svg",
            "mode": "tint",
            "color": "",
            "name": "cloud",
        },
    }
    calls = _run(
        {
            "project_slug": "demo",
            "locales": ["en"],
            "default_locale": "en",
            "services": [_repeater_svc({"items": [item]})],
        }
    )
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["item_schema"] == _SCHEMA
    put = next(c for c in calls if c[0] == "PUT")
    assert put[2]["content"]["_schema"] == _SCHEMA
    assert put[2]["content"]["items"] == [item]
