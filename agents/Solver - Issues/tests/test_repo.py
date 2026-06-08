"""Solver git-ops tests (mocked subprocess): staging-branch clone + commit + push.

Covers the S3.5 staging-branch model (clone cms-preview HEAD, plain push +
PushRejectedError) AND the SEC-001 hardening layered on top (token stripped from
origin after clone, re-injected only at push time, staged-diff secret scan).
"""

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


# ---- clone (staging-branch model + SEC-001 token strip) ----


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


def test_clone_at_preview_head_uses_token_then_strips_it(fake_run, tmp_path, monkeypatch):
    """SEC-001: the clone authenticates with the token, but origin must end
    tokenless so the secret isn't in .git/config during the untrusted Claude run."""
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))
    repo.clone_at_preview_head(
        repo_slug="owner/name",
        dev_branch="cms-preview",
        dest="./client-repo",
    )
    clone_url = next(a for a in fake_run[0]["args"] if a.startswith("https://"))
    assert "x-access-token:ghs_test@github.com/owner/name" in clone_url
    set_url_calls = [c for c in fake_run if "set-url" in c["args"]]
    assert set_url_calls, "expected origin to be rewritten after cloning"
    tokenless = next(a for a in set_url_calls[-1]["args"] if a.startswith("https://"))
    assert tokenless == "https://github.com/owner/name.git"
    assert "x-access-token" not in tokenless  # the token must be gone


def test_clone_at_preview_head_saves_current_sha(fake_run, tmp_path, monkeypatch):
    monkeypatch.setattr(repo, "PREV_SHA_PATH", str(tmp_path / "prev-solver-sha"))

    # Make `git rev-parse HEAD` return a deterministic sha.
    def run_with_sha(args, **kwargs):
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
    assert "solver@roman-technologies.dev" in str(user_email[0]["args"])
    assert "Solver Agent" in str(user_name[0]["args"])


# ---- has_diff ----


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


# ---- commit + push (plain push + PushRejectedError + SEC-001 re-auth/secret scan) ----


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


def test_commit_and_push_uses_plain_push_no_force(fake_run, tmp_path):
    sha = repo.commit_and_push(path=str(tmp_path), issue_id="i1", issue_title="t")  # noqa: F841
    push_calls = [c for c in fake_run if "push" in c["args"]]
    assert len(push_calls) == 1
    push_args = push_calls[0]["args"]
    assert "--force" not in str(push_args)
    assert "--force-with-lease" not in str(push_args)


def test_commit_and_push_raises_push_rejected_error(monkeypatch, tmp_path):
    """When git push exits non-zero, raise PushRejectedError instead of CalledProcessError."""
    from subprocess import CalledProcessError, CompletedProcess

    def run(args, **kwargs):
        if "push" in args:
            raise CalledProcessError(
                returncode=1,
                cmd=args,
                stderr="rejected — non-fast-forward",
            )
        return CompletedProcess(args=args, returncode=0, stdout="abc123\n", stderr="")

    monkeypatch.setattr(repo.subprocess, "run", run)
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")

    with pytest.raises(repo.PushRejectedError):
        repo.commit_and_push(path=str(tmp_path), issue_id="i1", issue_title="t")


def test_commit_and_push_reauths_origin_before_push(monkeypatch):
    """SEC-001: the token is re-injected into origin only at push time, and the
    set-url happens before the push."""
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "rev-parse" in args:
            result.stdout = "abc123\n"
        if "get-url" in args:
            result.stdout = "https://github.com/owner/name.git\n"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake)
    repo.commit_and_push(path="./client-repo", issue_id="i1", issue_title="t")

    set_url_idx = next(i for i, a in enumerate(calls) if "set-url" in a)
    push_idx = next(i for i, a in enumerate(calls) if "push" in a)
    assert set_url_idx < push_idx
    authed = next(a for a in calls[set_url_idx] if a.startswith("https://"))
    assert authed == "https://x-access-token:ghs_test@github.com/owner/name.git"


def test_push_refused_when_diff_contains_secret(monkeypatch):
    """SEC-001/SEC-056: a staged diff that introduces a credential is rejected
    before commit/push."""
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "diff" in args and "--cached" in args:
            result.stdout = (
                '+  const t = {"claudeAiOauth": {"accessToken": "sk-ant-abcdefghijklmnop"}}'
            )
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake)
    with pytest.raises(RuntimeError, match="refusing to push"):
        repo.commit_and_push(path="./client-repo", issue_id="i1", issue_title="t")
    # Must abort before committing or pushing.
    assert not any("commit" in a for a in calls)
    assert not any("push" in a for a in calls)


def test_push_allowed_for_clean_diff(monkeypatch):
    """A normal website fix (no secret-shaped content) pushes as usual."""
    monkeypatch.setenv("SOLVER_GITHUB_TOKEN", "ghs_test")
    calls = []

    def fake(args, **kwargs):
        calls.append(args)
        result = MagicMock()
        result.returncode = 0
        result.stdout = ""
        if "rev-parse" in args:
            result.stdout = "abc123\n"
        if "get-url" in args:
            result.stdout = "https://github.com/owner/name.git\n"
        if "diff" in args and "--cached" in args:
            result.stdout = "+  <h1>Fixed hero heading</h1>"
        return result

    monkeypatch.setattr(repo.subprocess, "run", fake)
    sha = repo.commit_and_push(path="./client-repo", issue_id="i1", issue_title="t")
    assert sha == "abc123"
    assert any("push" in a for a in calls)


def test_commit_truncates_long_title(fake_run, monkeypatch):
    monkeypatch.setattr(
        repo.subprocess, "run", lambda args, **kw: MagicMock(returncode=0, stdout="sha\n")
    )
    long_title = "a" * 200
    repo.commit_and_push(path="./client-repo", issue_id="issue-1", issue_title=long_title)
