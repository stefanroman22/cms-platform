"""Tests for the workflow's first step: claim + write outputs."""

from __future__ import annotations

import json

import claim_issue
import pytest


@pytest.fixture
def gh_output(tmp_path, monkeypatch):
    """Stub GITHUB_OUTPUT to a tmp file we can inspect."""
    output_path = tmp_path / "gh_output"
    output_path.write_text("")
    monkeypatch.setenv("GITHUB_OUTPUT", str(output_path))
    return output_path


@pytest.fixture
def tmp_files(tmp_path, monkeypatch):
    """Redirect /tmp paths to tmp_path so tests don't pollute the host."""
    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "agent-prompt.md"))
    return tmp_path


def test_no_actionable_issue_writes_false_output(monkeypatch, gh_output, tmp_files):
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)
    assert claim_issue.main() == 0
    out = gh_output.read_text()
    assert "has_issue=false" in out
    assert not (tmp_files / "issue.json").exists()
    assert not (tmp_files / "agent-prompt.md").exists()


def test_actionable_issue_writes_outputs_and_prompt(monkeypatch, gh_output, tmp_files):
    issue = {
        "id": "issue-1",
        "project_id": "proj-1",
        "title": "Hero broken",
        "description": "stretches on iPhone",
        "priority": "High",
        "status": "pending",
        "revision_feedback": None,
    }
    project = {
        "id": "proj-1",
        "slug": "acme",
        "name": "Acme",
        "github_repo": "stefan/acme",
        "repo_branch": "cms-preview",
    }
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: issue)
    monkeypatch.setattr(claim_issue.db, "fetch_project", lambda pid: project)

    assert claim_issue.main() == 0

    out = gh_output.read_text()
    assert "has_issue=true" in out
    assert "repo=stefan/acme" in out
    assert "branch=cms-preview" in out
    assert "issue_id=issue-1" in out

    issue_json = json.loads((tmp_files / "issue.json").read_text())
    assert issue_json["id"] == "issue-1"
    assert issue_json["project"]["slug"] == "acme"

    prompt = (tmp_files / "agent-prompt.md").read_text()
    assert "Hero broken" in prompt
    assert "stretches on iPhone" in prompt
    assert "Step 0 — Verify the issue is real" in prompt
    assert "Previous attempt was rejected" not in prompt  # no revision_feedback


def test_prompt_includes_revision_feedback_when_present(monkeypatch, gh_output, tmp_files):
    issue = {
        "id": "issue-2",
        "project_id": "proj-1",
        "title": "Footer year",
        "description": "should be 2026",
        "priority": "Low",
        "status": "in_progress",
        "revision_feedback": "the change you made broke the header",
    }
    project = {"slug": "acme", "github_repo": "stefan/acme", "repo_branch": "cms-preview"}
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: issue)
    monkeypatch.setattr(claim_issue.db, "fetch_project", lambda pid: project)

    claim_issue.main()
    prompt = (tmp_files / "agent-prompt.md").read_text()
    assert "Previous attempt was rejected" in prompt
    assert "the change you made broke the header" in prompt
