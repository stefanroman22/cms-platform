"""Git clone+reset + commit + push tests (mocked subprocess)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
import repo


@pytest.fixture
def fake_run(monkeypatch):
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    calls = []

    def run(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        result.stderr = ""
        return result

    monkeypatch.setattr(repo.subprocess, "run", run)
    return calls


def test_clone_and_reset_to_prod_clones_with_no_single_branch(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )
    clone_call = fake_run[0]
    assert clone_call["args"][0] == "git"
    assert "clone" in clone_call["args"]
    assert "--no-single-branch" in clone_call["args"]
    assert "--branch" in clone_call["args"]
    assert "main" in clone_call["args"]
    url = next(a for a in clone_call["args"] if a.startswith("https://"))
    assert "x-access-token:ghs_test@github.com/owner/name" in url


def test_clone_and_reset_configures_git_user(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )
    user_email = [c for c in fake_run if "user.email" in str(c["args"])]
    user_name = [c for c in fake_run if "user.name" in str(c["args"])]
    assert len(user_email) == 1
    assert len(user_name) == 1
    assert "solver@roman-technologies.dev" in str(user_email[0]["args"])
    assert "Solver Agent" in str(user_name[0]["args"])


def test_clone_and_reset_fetches_dev_branch_and_saves_prev_sha(tmp_path, monkeypatch):
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    prev_sha_path = tmp_path / "prev-solver-sha"
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(prev_sha_path))

    calls = []

    def fake_run_with_sha(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "rev-parse" in args and "origin/cms-preview" in args:
            result.stdout = "deadbeefcafebabe\n"
            result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )

    fetch_calls = [c for c in calls if "fetch" in c["args"]]
    assert any("cms-preview" in str(c["args"]) for c in fetch_calls)
    assert prev_sha_path.read_text().strip() == "deadbeefcafebabe"
    checkout_calls = [c for c in calls if "checkout" in c["args"]]
    assert any("-B" in c["args"] and "cms-preview" in c["args"] for c in checkout_calls)
    assert any("origin/main" in c["args"] for c in checkout_calls)


def test_clone_and_reset_handles_missing_dev_branch(tmp_path, monkeypatch):
    """First-run case: origin/cms-preview doesn't exist yet."""
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    prev_sha_path = tmp_path / "prev-solver-sha"
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(prev_sha_path))

    calls = []

    def fake_run_no_dev(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "fetch" in args and "cms-preview" in args:
            result.returncode = 128
            result.stderr = "fatal: couldn't find remote ref refs/heads/cms-preview\n"
        if "rev-parse" in args and "origin/cms-preview" in args:
            result.returncode = 128
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_no_dev)
    repo.clone_and_reset_to_prod(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        prod_branch="main",
        dest="./client-repo",
    )

    assert prev_sha_path.exists()
    assert prev_sha_path.read_text() == ""


def test_has_diff_returns_true_when_changes(fake_run, monkeypatch):
    def fake_run_with_diff(args, **kwargs):
        result = MagicMock()
        if "--quiet" in args:
            result.returncode = 1
        else:
            result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_diff)
    assert repo.has_diff("./client-repo") is True


def test_has_diff_returns_false_when_clean(fake_run, monkeypatch):
    def fake_run_clean(args, **kwargs):
        result = MagicMock()
        result.returncode = 0
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_clean)
    assert repo.has_diff("./client-repo") is False


def test_commit_uses_required_message_format(fake_run, monkeypatch):
    calls = []

    def fake_run_with_sha(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        if "rev-parse" in args:
            result.stdout = "abc123def4567\n"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)

    sha = repo.commit_and_push(
        path="./client-repo",
        issue_id="issue-1",
        issue_title="Hero broken",
    )

    assert sha == "abc123def4567"
    commit_call = next(c for c in calls if "commit" in c["args"])
    msg = next(a for a in commit_call["args"] if a.startswith("fix:"))
    assert "fix: Hero broken" in msg
    assert "Automated fix by Solver Agent" in msg
    assert "Co-Authored-By: Solver Agent" in msg


def test_commit_and_push_uses_force_with_lease(fake_run, monkeypatch):
    calls = []

    def fake_run_with_sha(args, **kwargs):
        calls.append({"args": args, "kwargs": kwargs})
        result = MagicMock()
        result.returncode = 0
        if "rev-parse" in args:
            result.stdout = "abc123\n"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake_run_with_sha)
    repo.commit_and_push(path="./client-repo", issue_id="i1", issue_title="t")
    push_call = next(c for c in calls if "push" in c["args"])
    assert "--force-with-lease" in push_call["args"]


def test_commit_truncates_long_title(fake_run, monkeypatch):
    monkeypatch.setattr(
        repo.subprocess, "run", lambda args, **kw: MagicMock(returncode=0, stdout="sha\n")
    )
    long_title = "a" * 200
    repo.commit_and_push(path="./client-repo", issue_id="issue-1", issue_title=long_title)
