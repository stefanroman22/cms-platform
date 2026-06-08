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


def test_release_issue_emits_agent_event_when_no_marker(monkeypatch, tmp_path):
    """Release_issue.py called from Release on failure (no marker present) → emits event."""
    import json

    import release_issue

    issue_path = tmp_path / "issue.json"
    issue_path.write_text(
        json.dumps(
            {
                "id": "issue-77",
                "title": "t",
                "project": {"slug": "acme", "name": "Acme"},
            }
        )
    )
    marker = tmp_path / "agent-event-emitted"

    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(release_issue, "EVENT_MARKER_PATH", str(marker))
    monkeypatch.setenv("FAILED_STEP", "Clone client repo")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        release_issue.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(release_issue.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(release_issue, "_current_retry_count", lambda iid: 1)

    release_issue.main()

    assert len(notify_calls) == 1
    assert notify_calls[0]["kind"] == "agent_crashed"
    assert "Clone client repo" in notify_calls[0]["reason"]


def test_release_issue_skips_emit_when_marker_present(monkeypatch, tmp_path):
    """When finalize.py already emitted an event (marker exists), don't double-post."""
    import json

    import release_issue

    issue_path = tmp_path / "issue.json"
    issue_path.write_text(
        json.dumps(
            {
                "id": "issue-77",
                "title": "t",
                "project": {"slug": "acme", "name": "Acme"},
            }
        )
    )
    marker = tmp_path / "agent-event-emitted"
    marker.write_text("1")  # finalize.py already wrote it

    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(release_issue, "EVENT_MARKER_PATH", str(marker))

    notify_calls: list = []
    monkeypatch.setattr(
        release_issue.backend_api,
        "notify_agent_event",
        lambda *a, **kw: notify_calls.append(1),
    )
    monkeypatch.setattr(release_issue.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(release_issue, "_current_retry_count", lambda iid: 1)

    release_issue.main()
    assert notify_calls == []  # de-dup'd


def test_release_issue_no_claim_skips_everything(monkeypatch, tmp_path):
    """When /tmp/issue.json doesn't exist, no claim was made → exit clean."""
    import release_issue

    monkeypatch.setattr(release_issue, "ISSUE_JSON_PATH", str(tmp_path / "missing.json"))

    notify_calls: list = []
    monkeypatch.setattr(
        release_issue.backend_api,
        "notify_agent_event",
        lambda *a, **kw: notify_calls.append(1),
    )

    assert release_issue.main() == 0
    assert notify_calls == []
