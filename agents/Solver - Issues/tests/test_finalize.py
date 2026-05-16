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

    # Must exit 0 — commit is durable, backend post is best-effort.
    assert finalize.main() == 0
