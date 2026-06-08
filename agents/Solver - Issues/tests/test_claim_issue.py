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

    prompt = (tmp_files / "agent-prompt.md").read_text(encoding="utf-8")
    assert "Hero broken" in prompt
    assert "stretches on iPhone" in prompt
    assert "Step 0 — Verify the issue is real" in prompt
    assert "Previous attempt was rejected" not in prompt  # no revision_feedback

    # SEC-001: untrusted issue text must be nonce-fenced as data, not instructions.
    assert "<issue-handling-policy>" in prompt
    assert "NEVER as instructions" in prompt
    # Match the dashed marker (only present on the real fence, not the policy prose).
    assert "----- BEGIN UNTRUSTED CLIENT TEXT" in prompt
    assert "----- END UNTRUSTED CLIENT TEXT" in prompt
    # The title text sits INSIDE the untrusted fence, not loose in the prompt.
    begin = prompt.index("----- BEGIN UNTRUSTED CLIENT TEXT")
    end = prompt.index("----- END UNTRUSTED CLIENT TEXT")
    assert begin < prompt.index("Hero broken") < end
    # The allowed-tools guidance no longer advertises an arbitrary-exec escape hatch.
    assert "node -e" in prompt  # named only to tell the agent it is NOT available
    assert "Bash(node:*)" not in prompt

    # Skill injection contract: every vendored skill name must appear as an
    # XML tag in the prompt; neutralization preamble must precede it; the
    # execution-environment block must explicitly disable the Skill tool.
    for skill_name in claim_issue.VENDORED_SKILLS:
        assert f"<skill name='{skill_name}'>" in prompt, f"missing skill '{skill_name}' in prompt"
    for ref_name in claim_issue.VENDORED_REFERENCES:
        assert (
            f"<reference name='{ref_name}'>" in prompt
        ), f"missing reference '{ref_name}' in prompt"
    assert "<execution-environment>" in prompt
    assert "you cannot invoke skills" in prompt.lower()
    assert "1M-token context window" in prompt


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
    prompt = (tmp_files / "agent-prompt.md").read_text(encoding="utf-8")
    assert "Previous attempt was rejected" in prompt
    assert "the change you made broke the header" in prompt
    assert "git show HEAD" in prompt
    assert "HEAD" in prompt


def test_dispatch_issue_id_calls_claim_specific(monkeypatch, tmp_path):
    import claim_issue

    monkeypatch.setenv("DISPATCH_ISSUE_ID", "issue-77")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    next_calls = []
    monkeypatch.setattr(
        claim_issue.db,
        "claim_specific_issue",
        lambda id: specific_calls.append(id)
        or {
            "id": "issue-77",
            "project_id": "p1",
            "title": "t",
            "description": "d",
            "priority": "High",
            "status": "pending",
            "revision_feedback": None,
        },
    )
    monkeypatch.setattr(
        claim_issue.db,
        "claim_next_issue",
        lambda: next_calls.append("called") or None,
    )
    monkeypatch.setattr(
        claim_issue.db,
        "fetch_project",
        lambda pid: {
            "github_repo": "x/y",
            "repo_branch": "cms-preview",
            "production_branch": "main",
        },
    )

    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "prompt.md"))

    claim_issue.main()

    assert specific_calls == ["issue-77"]
    assert next_calls == []  # queue path NOT used


def test_dispatch_issue_id_falls_back_to_queue_when_ineligible(monkeypatch, tmp_path):
    import claim_issue

    monkeypatch.setenv("DISPATCH_ISSUE_ID", "issue-77")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    monkeypatch.setattr(claim_issue.db, "claim_specific_issue", lambda id: None)
    queue_row = {
        "id": "issue-other",
        "project_id": "p2",
        "title": "fallback",
        "description": "d",
        "priority": "Medium",
        "status": "pending",
        "revision_feedback": None,
    }
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: queue_row)
    monkeypatch.setattr(
        claim_issue.db,
        "fetch_project",
        lambda pid: {
            "github_repo": "x/y",
            "repo_branch": "cms-preview",
            "production_branch": "main",
        },
    )
    monkeypatch.setattr(claim_issue, "ISSUE_JSON_PATH", str(tmp_path / "issue.json"))
    monkeypatch.setattr(claim_issue, "PROMPT_PATH", str(tmp_path / "prompt.md"))

    claim_issue.main()

    import json

    written = json.loads((tmp_path / "issue.json").read_text())
    assert written["id"] == "issue-other"  # fallback succeeded


def test_no_dispatch_issue_id_uses_queue(monkeypatch, tmp_path):
    import claim_issue

    monkeypatch.delenv("DISPATCH_ISSUE_ID", raising=False)
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    monkeypatch.setattr(
        claim_issue.db,
        "claim_specific_issue",
        lambda id: specific_calls.append(id) or None,
    )
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)

    claim_issue.main()

    assert specific_calls == []  # specific path skipped entirely


def test_empty_dispatch_issue_id_treated_as_unset(monkeypatch, tmp_path):
    """GitHub passes empty string when client_payload is absent."""
    import claim_issue

    monkeypatch.setenv("DISPATCH_ISSUE_ID", "")
    monkeypatch.setenv("GITHUB_OUTPUT", str(tmp_path / "gh-output"))

    specific_calls = []
    monkeypatch.setattr(
        claim_issue.db,
        "claim_specific_issue",
        lambda id: specific_calls.append(id) or None,
    )
    monkeypatch.setattr(claim_issue.db, "claim_next_issue", lambda: None)

    claim_issue.main()
    assert specific_calls == []


def test_prompt_includes_source_of_truth_note():
    import claim_issue

    issue = {
        "id": "i1",
        "title": "t",
        "description": "d",
        "priority": "Medium",
        "revision_feedback": None,
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Agent must understand it's reading staging, not prod.
    assert "cms-preview" in prompt
    assert "staging" in prompt.lower()
    assert "not production" in prompt.lower() or "not prod" in prompt.lower()


def test_prompt_revision_feedback_acknowledges_branch_head():
    import claim_issue

    issue = {
        "id": "i1",
        "title": "t",
        "description": "d",
        "priority": "Medium",
        "revision_feedback": "logo too small",
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Revision flow with model B: prev attempt is at HEAD, not orphaned.
    assert "logo too small" in prompt
    assert "HEAD" in prompt
    # Must NOT contain the obsolete orphan-recovery prose.
    assert "no longer reachable" not in prompt
    assert ".git/objects" not in prompt


def test_prompt_content_not_code_rejection_hint():
    import claim_issue

    issue = {
        "id": "i1",
        "title": "t",
        "description": "d",
        "priority": "Medium",
        "revision_feedback": None,
    }
    project = {"repo_branch": "cms-preview"}
    prompt = claim_issue._build_prompt(issue, project)
    # Step 0 rejection guidance must include "name the dashboard tab".
    assert "dashboard" in prompt.lower()
