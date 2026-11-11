"""Tests for the options service and toggle/select/color field types (ADR-0013).

Covers:
  1. The Phase-2 SYSTEM_PROMPT lists the `options` service, the option field types and
     the `readOptions` detection rule, and requires `item_schema` for options.
  2. cms.config.json records `type: "options"` and the options `schema` keys.
  3. Provisioning creates an options service with its `item_schema`, seeds it once
     (default locale only, even if marked translatable) as `{_schema, values}`, and
     repeater option fields keep `options`/`default` in the create and seed payloads.
"""

from __future__ import annotations

import json
import tempfile
from unittest.mock import MagicMock, patch

import output_writer
import prompts
import scan

_OPTIONS_SCHEMA = [
    {"key": "background", "label": "Background", "type": "color", "default": ""},
    {
        "key": "content_width",
        "label": "Content width",
        "type": "select",
        "options": [
            {"value": "narrow", "label": "Narrow"},
            {"value": "standard", "label": "Standard"},
            {"value": "wide", "label": "Wide"},
            {"value": "full", "label": "Full"},
        ],
        "default": "standard",
    },
    {"key": "show_map", "label": "Show map", "type": "toggle", "default": True},
]

_VALUES = {"background": "", "content_width": "standard", "show_map": True}


def _options_svc(initial_content: dict | None = None, **extra) -> dict:
    svc = {
        "service_key": "contact_page_options",
        "service_type_slug": "options",
        "label": "Contact page options",
        "page_name": "Contact",
        "display_order": 9,
        "translatable": False,
        "item_schema": _OPTIONS_SCHEMA,
        "initial_content": {"values": _VALUES} if initial_content is None else initial_content,
    }
    svc.update(extra)
    return svc


# ---------------------------------------------------------------------------
# 1. SYSTEM_PROMPT
# ---------------------------------------------------------------------------


def test_prompt_lists_options_service_and_field_types():
    p = prompts.SYSTEM_PROMPT
    assert "| options |" in p
    assert "string|inline|richtext|url|tags|slug|image|icon|toggle|select|color" in p
    assert "`toggle`" in p and "`select`" in p and "`color`" in p
    assert '"options"' in p and '"default"' in p


def test_prompt_detects_read_options_and_requires_item_schema():
    p = prompts.SYSTEM_PROMPT
    assert "readOptions(" in p
    assert "<page>_page_options" in p
    assert "`item_schema` is required only for `repeater` and `options`" in p
    assert "every `options` service are always `translatable: false`" in p


# ---------------------------------------------------------------------------
# 2. cms.config.json
# ---------------------------------------------------------------------------


def _config(manifest: dict) -> dict:
    with tempfile.TemporaryDirectory() as tmp:
        config_path, _ = output_writer.write_outputs(manifest, tmp)
        return json.loads(config_path.read_text(encoding="utf-8"))


def test_config_records_options_type_and_schema_keys():
    config = _config({"project_slug": "demo", "services": [_options_svc()]})
    assert config["services"]["contact_page_options"] == {
        "type": "options",
        "page": "Contact",
        "schema": {"background": "color", "content_width": "select", "show_map": "toggle"},
    }


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


def _multi(services: list[dict]) -> dict:
    return {
        "project_slug": "demo",
        "locales": ["en", "nl"],
        "default_locale": "en",
        "services": services,
    }


def test_options_service_created_with_item_schema():
    calls = _run(_multi([_options_svc()]))
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["service_type_slug"] == "options"
    assert post[2]["service_key"] == "contact_page_options"
    assert post[2]["page_name"] == "Contact"
    assert post[2]["item_schema"] == _OPTIONS_SCHEMA


def test_options_seeded_once_with_schema_and_values():
    calls = _run(_multi([_options_svc()]))
    puts = [c for c in calls if c[0] == "PUT"]
    assert len(puts) == 1
    assert "locale=" not in puts[0][1]
    assert puts[0][2]["content"] == {"values": _VALUES, "_schema": _OPTIONS_SCHEMA}


def test_options_never_seeded_per_locale_even_if_marked_translatable():
    svc = _options_svc(
        initial_content={"en": {"values": _VALUES}, "nl": {"values": _VALUES}},
        translatable=True,
    )
    calls = _run(_multi([svc]))
    puts = [c for c in calls if c[0] == "PUT"]
    assert len(puts) == 1
    assert "locale=" not in puts[0][1]
    assert puts[0][2]["content"]["values"] == _VALUES


def test_options_flat_seed_is_wrapped_into_values():
    assert scan._options_seed_content(_options_svc(), dict(_VALUES)) == {
        "values": _VALUES,
        "_schema": _OPTIONS_SCHEMA,
    }


def test_options_seed_keeps_existing_schema_and_ignores_other_types():
    own = [{"key": "background", "label": "Bg", "type": "color"}]
    content = {"_schema": own, "values": {"background": "#ffffff"}}
    assert scan._options_seed_content(_options_svc(), content) == content
    repeater = {"service_type_slug": "repeater", "item_schema": _OPTIONS_SCHEMA}
    assert scan._options_seed_content(repeater, {"items": []}) == {"items": []}


def test_repeater_option_fields_reach_create_and_seed():
    schema = [
        {"key": "title", "label": "Title", "type": "inline"},
        {"key": "show_title", "label": "Show title", "type": "toggle", "default": True},
        {
            "key": "image_position",
            "label": "Image position",
            "type": "select",
            "options": [{"value": "left", "label": "Left"}, {"value": "right", "label": "Right"}],
            "default": "left",
        },
    ]
    item = {"title": "Cloud", "show_title": False, "image_position": "right"}
    svc = {
        "service_key": "services_list",
        "service_type_slug": "repeater",
        "label": "Services",
        "page_name": "Services",
        "item_schema": schema,
        "initial_content": {"items": [item]},
    }
    calls = _run(
        {"project_slug": "demo", "locales": ["en"], "default_locale": "en", "services": [svc]}
    )
    post = next(c for c in calls if c[0] == "POST")
    assert post[2]["item_schema"] == schema
    put = next(c for c in calls if c[0] == "PUT")
    assert put[2]["content"]["_schema"] == schema
    assert put[2]["content"]["items"] == [item]
