"""
Tests for i18n additions to output_writer.write_outputs.

Covers:
  1. Multi-locale manifest: cms.config.json includes `locales` and `defaultLocale`
     sourced from manifest `locales`/`default_locale`.
  2. Manifest without locale fields: cms.config.json falls back to ["en"] / "en".
  3. cms-provision.json always dumps the full manifest (including per-locale
     initial_content when present).
"""

from __future__ import annotations

import json
import tempfile

import output_writer

# ---------------------------------------------------------------------------
# Test 1: Multi-locale manifest → locales + defaultLocale in cms.config.json
# ---------------------------------------------------------------------------


def test_multi_locale_manifest_emits_locales_in_config():
    manifest = {
        "project_slug": "demo",
        "locales": ["en", "nl"],
        "default_locale": "en",
        "services": [
            {
                "service_key": "hero",
                "service_type_slug": "text_block",
                "page_name": "Home",
                "initial_content": {
                    "en": {"title": "Hello"},
                    "nl": {"title": "Hallo"},
                },
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        config_path, provision_path = output_writer.write_outputs(manifest, tmp)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["locales"] == [
            "en",
            "nl",
        ], f"Expected locales=['en','nl'], got {config.get('locales')}"
        assert (
            config["defaultLocale"] == "en"
        ), f"Expected defaultLocale='en', got {config.get('defaultLocale')}"

        # cms-provision.json must carry the full manifest (including per-locale content)
        provision = json.loads(provision_path.read_text(encoding="utf-8"))
        assert provision == manifest, "cms-provision.json must equal the full manifest"


# ---------------------------------------------------------------------------
# Test 2: Manifest without locale fields → back-compat defaults
# ---------------------------------------------------------------------------


def test_manifest_without_locales_defaults_to_en():
    manifest = {
        "project_slug": "legacy-site",
        "services": [
            {
                "service_key": "about",
                "service_type_slug": "text_block",
                "page_name": "About",
                "initial_content": {"body": "We are a team."},
            }
        ],
    }

    with tempfile.TemporaryDirectory() as tmp:
        config_path, _ = output_writer.write_outputs(manifest, tmp)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["locales"] == [
            "en"
        ], f"Expected fallback locales=['en'], got {config.get('locales')}"
        assert (
            config["defaultLocale"] == "en"
        ), f"Expected fallback defaultLocale='en', got {config.get('defaultLocale')}"


# ---------------------------------------------------------------------------
# Test 3: Single non-English locale → correct values passed through
# ---------------------------------------------------------------------------


def test_single_non_english_locale_passed_through():
    manifest = {
        "project_slug": "acasa",
        "locales": ["ro"],
        "default_locale": "ro",
        "services": [],
    }

    with tempfile.TemporaryDirectory() as tmp:
        config_path, _ = output_writer.write_outputs(manifest, tmp)

        config = json.loads(config_path.read_text(encoding="utf-8"))
        assert config["locales"] == ["ro"]
        assert config["defaultLocale"] == "ro"
