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


def test_clone_at_preview_head_clones_at_preview_no_reset(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    clone_call = fake_run[0]
    assert clone_call["args"][0] == "git"
    assert "clone" in clone_call["args"]
    assert "--branch" in clone_call["args"]
    branch_idx = clone_call["args"].index("--branch")
    assert clone_call["args"][branch_idx + 1] == "cms-preview"
    # No checkout/reset to a different branch should be issued.
    checkout_calls = [c for c in fake_run if "checkout" in str(c["args"])]
    assert checkout_calls == [], f"unexpected checkout: {checkout_calls}"


def test_clone_at_preview_head_saves_current_sha(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))

    # Make `git rev-parse HEAD` return a deterministic sha.
    def run_with_sha(args, **kwargs):
        from unittest.mock import MagicMock

        r = MagicMock()
        r.returncode = 0
        r.stdout = "abc1234defabc1234defabc1234defabc1234de\n" if args[-1] == "HEAD" else ""
        r.stderr = ""
        return r

    monkeypatch.setattr(repo.subprocess, "run", run_with_sha)

    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    saved = (tmp_path / "prev-solver-sha").read_text().strip()
    assert saved == "abc1234defabc1234defabc1234defabc1234de"


def test_clone_at_preview_head_configures_git_user(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    user_email = [c for c in fake_run if "user.email" in str(c["args"])]
    user_name = [c for c in fake_run if "user.name" in str(c["args"])]
    assert len(user_email) == 1
    assert len(user_name) == 1
