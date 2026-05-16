"""Release + retry counter behavior tests."""

from __future__ import annotations

from unittest.mock import MagicMock

import db
import pytest


@pytest.fixture
def stub_sb(monkeypatch):
    monkeypatch.setenv("SUPABASE_URL", "http://localhost")
    monkeypatch.setenv("SUPABASE_SERVICE_ROLE_KEY", "key")
    monkeypatch.setenv("SOLVER_MAX_RETRIES", "3")

    sb = MagicMock()
    for m in ("table", "select", "eq", "single", "update", "execute"):
        getattr(sb, m).return_value = sb

    monkeypatch.setattr(db, "_supabase", lambda: sb)
    return sb


def test_release_failed_increments_retry_below_max(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 1})
    db.release_issue_failed("issue-1", "transient")
    update_payloads = [c.args[0] for c in stub_sb.update.call_args_list if c.args]
    assert len(update_payloads) == 1
    p = update_payloads[0]
    assert p["agent_status"] == "failed"
    assert p["agent_retry_count"] == 2
    assert p["agent_last_error"] == "transient"
    assert p["agent_claimed_at"] is None


def test_release_failed_marks_blocked_at_max(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 2})
    db.release_issue_failed("issue-1", "third strike")
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert p["agent_status"] == "blocked"
    assert p["agent_retry_count"] == 3


def test_release_failed_truncates_long_error(stub_sb):
    stub_sb.execute.return_value = MagicMock(data={"agent_retry_count": 0})
    db.release_issue_failed("issue-1", "x" * 1000)
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert len(p["agent_last_error"]) == 500


def test_mark_done_writes_commit_sha_and_clears_lock(stub_sb):
    db.mark_done("issue-1", commit_sha="abc1234def")
    p = [c.args[0] for c in stub_sb.update.call_args_list if c.args][0]
    assert p["agent_commit_sha"] == "abc1234def"
    assert p["agent_status"] is None
    assert p["agent_claimed_at"] is None
