"""Tests for finalize.py — the post-agent-step handler."""

from __future__ import annotations

import json

import finalize
import pytest


@pytest.fixture
def issue_payload(tmp_path, monkeypatch):
    issue = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "Hero broken",
        "description": "stretches",
        "priority": "High",
        "status": "pending",
        "project": {
            "slug": "acme",
            "github_repo": "stefan/acme",
            "repo_branch": "cms-preview",
        },
    }
    issue_path = tmp_path / "issue.json"
    issue_path.write_text(json.dumps(issue))
    status_path = tmp_path / "agent-status.md"

    monkeypatch.setattr(finalize, "ISSUE_JSON_PATH", str(issue_path))
    monkeypatch.setattr(finalize, "STATUS_MD_PATH", str(status_path))
    monkeypatch.setattr(finalize, "REPO_DIR", "./client-repo")

    return {"issue": issue, "issue_path": issue_path, "status_path": status_path}


def test_agent_status_md_cannot_reproduce_marks_failed(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot reproduce: hero section already responsive")

    release_calls = []
    monkeypatch.setattr(
        finalize.db,
        "release_issue_failed",
        lambda iid, err: release_calls.append({"id": iid, "err": err}),
    )
    # New behaviour: notify_agent_event is called before release_issue_failed.
    monkeypatch.setattr(finalize.backend_api, "notify_agent_event", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    assert finalize.main() == 0
    assert len(release_calls) == 1
    assert "Cannot reproduce" in release_calls[0]["err"]


def test_agent_status_md_cannot_fix_marks_failed(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot fix: too complex")

    release_calls = []
    monkeypatch.setattr(
        finalize.db, "release_issue_failed", lambda iid, err: release_calls.append(err)
    )
    # New behaviour: notify_agent_event is called before release_issue_failed.
    monkeypatch.setattr(finalize.backend_api, "notify_agent_event", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    finalize.main()
    assert "Cannot fix" in release_calls[0]


def test_empty_diff_marks_failed(monkeypatch, issue_payload):
    release_calls = []
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)
    monkeypatch.setattr(
        finalize.db, "release_issue_failed", lambda iid, err: release_calls.append(err)
    )
    # New behaviour: notify_agent_event is called before release_issue_failed.
    monkeypatch.setattr(finalize.backend_api, "notify_agent_event", lambda *a, **kw: None)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    finalize.main()
    assert any("no file changes" in e for e in release_calls)


def test_happy_path_commits_pushes_marks_done(monkeypatch, issue_payload):
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo,
        "commit_and_push",
        lambda **kw: "abc1234def5678",
    )

    mark_done_calls = []
    monkeypatch.setattr(
        finalize.db, "mark_done", lambda iid, commit_sha: mark_done_calls.append((iid, commit_sha))
    )

    backend_calls = []
    monkeypatch.setattr(
        finalize.backend_api,
        "trigger_issue_resolved",
        lambda iid: backend_calls.append(iid) or {},
    )

    assert finalize.main() == 0
    assert mark_done_calls == [("issue-1", "abc1234def5678")]
    assert backend_calls == ["issue-1"]


def test_backend_5xx_does_not_fail_finalize(monkeypatch, issue_payload):
    import requests

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "sha123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)

    def fake_trigger(iid):
        raise requests.HTTPError("500 Internal Server Error")

    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", fake_trigger)
    monkeypatch.setattr(finalize, "_fetch_slack_created_ts", lambda iid: None, raising=False)
    import slack as slack_client

    monkeypatch.setattr(slack_client, "post_thread_event_direct", lambda **kw: None)

    # Must exit 0 — commit is durable, backend post is best-effort.
    assert finalize.main() == 0


def test_status_md_rejected_calls_notify_agent_event(monkeypatch, issue_payload):
    issue_payload["status_path"].write_text("Cannot reproduce: x")
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append(
            {"iid": iid, "kind": kind, "reason": reason}
        ),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    assert finalize.main() == 0
    assert len(notify_calls) == 1
    assert notify_calls[0]["kind"] == "rejected"
    assert "Cannot reproduce" in notify_calls[0]["reason"]


def test_claude_exit_nonzero_calls_notify_agent_crashed(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "1")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    assert finalize.main() == 0
    assert notify_calls[0]["kind"] == "agent_crashed"
    assert "exit 1" in notify_calls[0]["reason"].lower()


def test_no_diff_calls_notify_no_diff(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: False)

    assert finalize.main() == 0
    assert notify_calls[0]["kind"] == "no_diff"


def test_push_rejected_calls_notify_backend_error_and_reraises(monkeypatch, issue_payload):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    notify_calls: list[dict] = []
    monkeypatch.setattr(
        finalize.backend_api,
        "notify_agent_event",
        lambda iid, *, kind, reason: notify_calls.append({"kind": kind, "reason": reason}),
    )
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)

    def push_fail(**kw):
        raise finalize.repo.PushRejectedError("rejected — non-fast-forward")

    monkeypatch.setattr(finalize.repo, "commit_and_push", push_fail)

    with pytest.raises(finalize.repo.PushRejectedError):
        finalize.main()
    assert notify_calls[0]["kind"] == "backend_error"
    assert "moved during run" in notify_calls[0]["reason"]


def test_backend_trigger_failure_falls_back_to_direct_slack(monkeypatch, issue_payload, tmp_path):
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "abc123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)

    def boom(issue_id):
        from requests.exceptions import HTTPError

        raise HTTPError("500 after retries")

    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", boom)

    # Need slack_created_ts lookup — stub via supabase or environment.
    monkeypatch.setattr(
        finalize,
        "_fetch_slack_created_ts",
        lambda iid: "ts-original",
        raising=False,  # function may not exist yet — defined in impl step
    )

    direct_calls: list[dict] = []
    import slack as slack_client

    monkeypatch.setattr(
        slack_client,
        "post_thread_event_direct",
        lambda **kw: direct_calls.append(kw),
    )

    assert finalize.main() == 0  # commit is durable; exit 0
    assert direct_calls[0]["kind"] == "backend_error"


def test_happy_path_writes_event_marker(monkeypatch, issue_payload, tmp_path):
    """Successful flows should write /tmp/agent-event-emitted only when an event was emitted."""
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")
    marker = tmp_path / "agent-event-emitted"
    monkeypatch.setattr(finalize, "EVENT_MARKER_PATH", str(marker))

    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(finalize.repo, "commit_and_push", lambda **kw: "abc123")
    monkeypatch.setattr(finalize.db, "mark_done", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.backend_api, "trigger_issue_resolved", lambda iid: {"ok": True})

    finalize.main()
    # Happy path emits NO agent event → marker should NOT exist.
    assert not marker.exists()


def test_event_emission_writes_marker(monkeypatch, issue_payload, tmp_path):
    """Any branch that calls notify_agent_event must write the marker."""
    issue_payload["status_path"].write_text("Cannot reproduce: x")
    monkeypatch.setenv("CLAUDE_EXIT_CODE", "0")
    marker = tmp_path / "agent-event-emitted"
    monkeypatch.setattr(finalize, "EVENT_MARKER_PATH", str(marker))

    monkeypatch.setattr(finalize.backend_api, "notify_agent_event", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.db, "release_issue_failed", lambda *a, **kw: None)
    monkeypatch.setattr(finalize.repo, "has_diff", lambda p: True)
    monkeypatch.setattr(
        finalize.repo, "commit_and_push", lambda **kw: pytest.fail("should not push")
    )

    finalize.main()
    assert marker.exists()
