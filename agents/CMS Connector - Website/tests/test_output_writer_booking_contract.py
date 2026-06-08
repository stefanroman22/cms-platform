"""
Tests for booking-contract enforcement in output_writer.write_outputs.

The connector maps the client form's fields to the SDK contract and records the
binding in cms.config.json (contractVersion + fieldMapping). A miswired form
that fails to map a required contract field must be caught at provisioning — the
writer raises so the test matrix fails, not production.

Covers:
  1. A complete field_mapping → cms.config.json carries booking.contractVersion +
     booking.fieldMapping.
  2. A mapping missing a required contract field → write_outputs raises.
  3. Back-compat: a booking block with no field_mapping still writes (the mapping
     is optional metadata; enforcement only triggers when a mapping is supplied).
"""

from __future__ import annotations

import json

import output_writer
import pytest
from output_writer import BOOKING_CONTRACT_VERSION, BOOKING_REQUIRED_FIELDS

# A client form whose fields are all mapped onto the required contract fields.
COMPLETE_MAPPING = {
    "service_id": "selectedServiceId",
    "start_utc": "slotStartIso",
    "customer.name": "fullName",
    "customer.email": "emailAddress",
}


def _manifest(field_mapping):
    return {
        "project_slug": "acme",
        "framework": "next",
        "cms_endpoint": "https://cms-backend-roman.vercel.app/content",
        "services": [],
        "booking": {
            "detected": True,
            "public_slug": "acme",
            "field_mapping": field_mapping,
        },
    }


def test_config_carries_contract_version_and_field_mapping(tmp_path):
    config_path, _ = output_writer.write_outputs(_manifest(COMPLETE_MAPPING), tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["booking"]["contractVersion"] == BOOKING_CONTRACT_VERSION
    assert config["booking"]["fieldMapping"] == COMPLETE_MAPPING
    # Spot-check it still carries slug + apiBase (back-compat).
    assert config["booking"]["slug"] == "acme"
    assert config["booking"]["apiBase"] == "https://cms-backend-roman.vercel.app/booking"


def test_missing_required_field_in_mapping_raises(tmp_path):
    bad = dict(COMPLETE_MAPPING)
    del bad["customer.email"]
    with pytest.raises(ValueError) as exc:
        output_writer.write_outputs(_manifest(bad), tmp_path)
    # The error names the unmapped required field so the matrix failure is actionable.
    assert "customer.email" in str(exc.value)


def test_all_required_fields_enforced(tmp_path):
    """Every required contract field individually triggers the failure."""
    for field in BOOKING_REQUIRED_FIELDS:
        bad = {k: v for k, v in COMPLETE_MAPPING.items() if k != field}
        with pytest.raises(ValueError) as exc:
            output_writer.write_outputs(_manifest(bad), tmp_path)
        assert field in str(exc.value)


def test_booking_without_field_mapping_still_writes(tmp_path):
    """A booking block without a field_mapping keeps the prior behaviour (slug +
    apiBase only); enforcement only kicks in once a mapping is provided."""
    manifest = {
        "project_slug": "acme",
        "framework": "next",
        "cms_endpoint": "https://cms-backend-roman.vercel.app/content",
        "services": [],
        "booking": {"detected": True, "public_slug": "acme"},
    }
    config_path, _ = output_writer.write_outputs(manifest, tmp_path)
    config = json.loads(config_path.read_text(encoding="utf-8"))
    assert config["booking"]["slug"] == "acme"
    assert "fieldMapping" not in config["booking"]
