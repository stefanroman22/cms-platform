"""Tests for booking-detection instructions in the Phase-2 SYSTEM_PROMPT."""

import prompts


def _prompt() -> str:
    return prompts.build_system_prompt()


def test_prompt_instructs_booking_detection():
    p = _prompt().lower()
    assert "booking" in p
    assert "scheduling" in p or "appointment" in p


def test_prompt_documents_booking_manifest_block():
    p = _prompt()
    assert '"booking"' in p
    for field in ["public_slug", "services", "resources", "hours", "destination_email"]:
        assert field in p
