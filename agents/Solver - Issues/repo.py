"""Git operations for the Solver Agent.

Shallow clone, has-diff check, commit-and-push. Token-authed via
SOLVER_GITHUB_TOKEN env. Uses subprocess directly — no GitPython dep.
"""

from __future__ import annotations

import os
import subprocess

_GIT_USER_EMAIL = "solver@roman-technologies.dev"
_GIT_USER_NAME = "Solver Agent"
_MAX_TITLE_LEN = 60


def _token() -> str:
    return os.environ["SOLVER_GITHUB_TOKEN"]


def _run(
    args: list[str], cwd: str | None = None, check: bool = True
) -> subprocess.CompletedProcess:
    return subprocess.run(args, cwd=cwd, capture_output=True, text=True, check=check)


def clone(repo: str, branch: str, dest: str) -> None:
    """Shallow-clone repo (owner/name) at branch into dest.

    Embeds SOLVER_GITHUB_TOKEN in the HTTPS URL via the x-access-token user.
    """
    url = f"https://x-access-token:{_token()}@github.com/{repo}.git"
    _run(["git", "clone", "--depth", "50", "--branch", branch, url, dest])
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])


def has_diff(path: str) -> bool:
    """True iff there are uncommitted changes in path's working tree."""
    result = _run(["git", "-C", path, "diff", "--quiet"], check=False)
    return result.returncode != 0


def commit_and_push(*, path: str, issue_id: str, issue_title: str) -> str:
    """Stage all changes, commit, push current HEAD to origin.

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
    _run(["git", "-C", path, "push", "origin", "HEAD"])
    return sha
