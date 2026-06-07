"""IssueCreateRequest input hardening (SEC-001 defense-in-depth)."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from auth_service.models.schemas import IssueCreateRequest


def test_strips_c0_control_chars_but_keeps_whitespace():
    req = IssueCreateRequest(
        title="Hero\x00 broken\x1b[31m",
        description="line1\nline2\twith tab\x07bell",
        priority="Low",
    )
    # NUL and ESC removed; printable bracket text kept.
    assert req.title == "Hero broken[31m"
    assert "\x00" not in req.title and "\x1b" not in req.title
    # newline + tab preserved; BEL removed.
    assert req.description == "line1\nline2\twith tabbell"


def test_all_control_char_title_fails_min_length():
    # Cleaned value is empty, so the min_length=1 bound rejects it (422 upstream).
    with pytest.raises(ValidationError):
        IssueCreateRequest(title="\x00\x01\x02", description="ok", priority="Low")


def test_clean_input_is_unchanged():
    req = IssueCreateRequest(title="Hero broken", description="stretches", priority="High")
    assert req.title == "Hero broken"
    assert req.description == "stretches"
