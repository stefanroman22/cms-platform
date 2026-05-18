"""Git operations for the Solver Agent.

Clone cms-preview at current HEAD (staging-branch model), has-diff check,
commit-and-push. Token-authed via SOLVER_GITHUB_TOKEN.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_GIT_USER_EMAIL = "solver@roman-technologies.dev"
_GIT_USER_NAME = "Solver Agent"
_MAX_TITLE_LEN = 60


class PushRejectedError(Exception):
    """Raised when git push fails because the remote branch moved.

    The runner workspace is ephemeral — when this is raised, the local
    commit cannot be recovered. finalize.py catches this and emits a
    distinct Slack event (kind=backend_error, "cms-preview moved during run").
    """


PREV_SHA_PATH = "/tmp/prev-solver-sha"


def _token() -> str:
    return os.environ["SOLVER_GITHUB_TOKEN"]


def _run(
    args: list[str], cwd: str | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def clone_at_preview_head(*, repo_slug: str, dev_branch: str, dest: str) -> None:
    """Clone client repo at dev_branch HEAD (no reset).

    With the staging-branch model (S3.5), cms-preview is a real staging
    branch — manual edits and prior unapproved solver attempts are preserved
    across runs. PREV_SHA_PATH stores the cloned HEAD SHA so revision-feedback
    retries can diff against the prior attempt's commit.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo_slug}.git"

    _run(
        [
            "git",
            "clone",
            "--depth",
            "50",
            "--branch",
            dev_branch,
            url,
            dest,
        ]
    )
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])

    # Save current HEAD for revision-feedback diff context.
    sha_result = _run(["git", "-C", dest, "rev-parse", "HEAD"], check=False)
    prev_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
    Path(PREV_SHA_PATH).write_text(prev_sha)


def has_diff(path: str) -> bool:
    """True iff there are uncommitted changes in path's working tree."""
    result = _run(["git", "-C", path, "diff", "--quiet"], check=False)
    return result.returncode != 0


def commit_and_push(*, path: str, issue_id: str, issue_title: str) -> str:
    """Stage all changes, commit, push current HEAD to origin (plain push).

    Plain `git push` (no --force-with-lease) — cms-preview is now a real
    staging branch with potentially-meaningful state. If the remote moved
    during the run, raise PushRejectedError so finalize.py can emit the
    distinct "branch moved" Slack event.

    Returns the new HEAD SHA on success.
    """
    short_title = issue_title[:_MAX_TITLE_LEN]
    message = (
        f"fix: {short_title}\n\n"
        f"Automated fix by Solver Agent for CMS issue {issue_id}.\n\n"
        f"Co-Authored-By: Solver Agent (Claude Code) <{_GIT_USER_EMAIL}>"
    )
    _run(["git", "-C", path, "add", "-A"])
    _run(["git", "-C", path, "commit", "-m", message])
    sha_result = _run(["git", "-C", path, "rev-parse", "HEAD"])
    sha = sha_result.stdout.strip()
    try:
        _run(["git", "-C", path, "push", "origin", "HEAD"])
    except subprocess.CalledProcessError as e:
        raise PushRejectedError(
            f"git push to {path} HEAD failed: {e.stderr or e.stdout or 'unknown'}"
        ) from e
    return sha
