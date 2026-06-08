"""
Tests for booking block additions to output_writer.write_outputs.

Covers:
  1. Manifest with booking detected: cms.config.json includes a "booking" object
     with "slug" and "apiBase".
  2. Manifest without booking block: cms.config.json has no "booking" key (back-compat).
"""

from __future__ import annotations

import json

import output_writer


def test_cms_config_includes_booking_when_detected(tmp_path):
    manifest = {
        "project_slug": "acme",
        "framework": "next",
        "cms_endpoint": "https://cms-backend-roman.vercel.app/content",
        "services": [],
        "booking": {"detected": True, "public_slug": "acme"},
    }

    config_path, _ = output_writer.write_outputs(manifest, tmp_path)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert (
        "booking" in config
    ), "cms.config.json must contain a 'booking' key when booking is detected"
    assert (
        config["booking"]["slug"] == "acme"
    ), f"Expected booking.slug='acme', got {config['booking'].get('slug')}"
    assert config["booking"]["apiBase"] == "https://cms-backend-roman.vercel.app/booking", (
        f"Expected booking.apiBase='https://cms-backend-roman.vercel.app/booking', "
        f"got {config['booking'].get('apiBase')}"
    )


def test_cms_config_omits_booking_when_absent(tmp_path):
    manifest = {
        "project_slug": "acme",
        "framework": "next",
        "cms_endpoint": "https://cms-backend-roman.vercel.app/content",
        "services": [],
    }

    config_path, _ = output_writer.write_outputs(manifest, tmp_path)

    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert (
        "booking" not in config
    ), "cms.config.json must NOT contain a 'booking' key when booking is absent"
