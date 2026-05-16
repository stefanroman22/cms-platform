"""Git operations for the Solver Agent.

Clone+reset (so cms-preview always starts from production HEAD),
has-diff check, commit-and-force-push. Token-authed via SOLVER_GITHUB_TOKEN.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

_GIT_USER_EMAIL = "solver@roman-technologies.dev"
_GIT_USER_NAME = "Solver Agent"
_MAX_TITLE_LEN = 60

PREV_SHA_PATH = "/tmp/prev-solver-sha"


def _token() -> str:
    return os.environ["SOLVER_GITHUB_TOKEN"]


def _run(
    args: list[str], cwd: str | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def clone_and_reset_to_prod(
    *, repo_slug: str, dev_branch: str, prod_branch: str, dest: str
) -> None:
    """Clone client repo, fetch dev_branch, reset working tree to prod_branch HEAD.

    Guarantees the agent always edits from current production state so the
    S1.5 listener can fast-forward production to cms-preview after the fix.

    Previous dev_branch SHA is saved to PREV_SHA_PATH (empty on first run);
    revision-feedback prompt uses it via `git show <sha>` since the object
    stays in .git/objects after the branch ref moves.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo_slug}.git"

    _run(
        [
            "git",
            "clone",
            "--depth",
            "50",
            "--no-single-branch",
            "--branch",
            prod_branch,
            url,
            dest,
        ]
    )
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])

    fetch_result = _run(
        ["git", "-C", dest, "fetch", "--depth", "50", "origin", dev_branch],
        check=False,
    )

    prev_sha = ""
    if fetch_result.returncode == 0:
        rev_parse = _run(
            ["git", "-C", dest, "rev-parse", f"origin/{dev_branch}"],
            check=False,
        )
        if rev_parse.returncode == 0:
            prev_sha = rev_parse.stdout.strip()

    Path(PREV_SHA_PATH).write_text(prev_sha)

    _run(["git", "-C", dest, "checkout", "-B", dev_branch, f"origin/{prod_branch}"])


def has_diff(path: str) -> bool:
    """True iff there are uncommitted changes in path's working tree."""
    result = _run(["git", "-C", path, "diff", "--quiet"], check=False)
    return result.returncode != 0


def commit_and_push(*, path: str, issue_id: str, issue_title: str) -> str:
    """Stage all changes, commit, force-with-lease push current HEAD to origin.

    Returns the new HEAD SHA.
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
    _run(["git", "-C", path, "push", "--force-with-lease", "origin", "HEAD"])
    return sha
