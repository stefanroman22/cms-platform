"""Git operations for the Solver Agent.

Clone cms-preview at current HEAD (staging-branch model), has-diff check,
commit-and-push. Token-authed via SOLVER_GITHUB_TOKEN.
"""

from __future__ import annotations

import os
import re
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

# SECURITY (SEC-001 / SEC-056): the agent runs over UNTRUSTED client issue text
# and could be injected into reading a runner secret (the Claude OAuth token, a
# private key, etc.) and writing it into a repo file so it rides the push out to
# the client repo / preview deployment. Before pushing, refuse any diff that
# introduces something matching these credential shapes — a committed secret is
# never a legitimate website fix. False positives release the issue as failed
# (safe) rather than leaking.
_SECRET_PATTERNS = (
    r"claudeAiOauth",  # marker from $HOME/.claude/.credentials.json
    r"sk-ant-[A-Za-z0-9_-]{16,}",  # Anthropic API key
    r"gh[pousr]_[A-Za-z0-9]{20,}",  # GitHub PAT / OAuth / server token
    r"github_pat_[A-Za-z0-9_]{20,}",  # GitHub fine-grained PAT
    r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----",  # private keys
    r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}",  # JWT (e.g. service-role key)
)


def _token() -> str:
    return os.environ["SOLVER_GITHUB_TOKEN"]


def _tokenless_url(repo_slug: str) -> str:
    return f"https://github.com/{repo_slug}.git"


def _authed_url(repo_slug: str) -> str:
    return f"https://x-access-token:{_token()}@github.com/{repo_slug}.git"


def _origin_repo_slug(path: str) -> str:
    """Recover `owner/name` from the (tokenless) origin URL set after cloning."""
    url = _run(["git", "-C", path, "remote", "get-url", "origin"]).stdout.strip()
    slug = url.removeprefix("https://github.com/").removesuffix(".git")
    return slug


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
    _run(
        [
            "git",
            "clone",
            "--depth",
            "50",
            "--branch",
            dev_branch,
            _authed_url(repo_slug),
            dest,
        ]
    )
    _run(["git", "-C", dest, "config", "user.email", _GIT_USER_EMAIL])
    _run(["git", "-C", dest, "config", "user.name", _GIT_USER_NAME])

    # Save current HEAD for revision-feedback diff context.
    sha_result = _run(["git", "-C", dest, "rev-parse", "HEAD"], check=False)
    prev_sha = sha_result.stdout.strip() if sha_result.returncode == 0 else ""
    Path(PREV_SHA_PATH).write_text(prev_sha)

    # SECURITY (SEC-001): the clone embedded SOLVER_GITHUB_TOKEN in origin's URL,
    # which git persisted to ./client-repo/.git/config. The next workflow step
    # runs the autonomous Claude agent over UNTRUSTED client issue text with this
    # repo as its cwd, so leaving the token in .git/config makes it readable by
    # an injected agent. Now that all clone-time network ops are done, rewrite
    # origin to a tokenless URL; commit_and_push re-auths it transiently at push
    # time (after the untrusted step). No secret remains on disk during the run.
    _run(["git", "-C", dest, "remote", "set-url", "origin", _tokenless_url(repo_slug)])


def has_diff(path: str) -> bool:
    """True iff there are uncommitted changes in path's working tree."""
    result = _run(["git", "-C", path, "diff", "--quiet"], check=False)
    return result.returncode != 0


def _assert_no_secrets_in_staged_diff(path: str) -> None:
    """Refuse to push if the staged diff introduces anything secret-shaped.

    Defense-in-depth against an injected agent exfiltrating a runner secret by
    writing it into a committed file (SEC-001 / SEC-056). Raises RuntimeError so
    the workflow's failure path releases the issue instead of pushing.
    """
    raw = _run(["git", "-C", path, "diff", "--cached"], check=False).stdout
    diff = raw if isinstance(raw, str) else ""
    for pattern in _SECRET_PATTERNS:
        if re.search(pattern, diff):
            raise RuntimeError(
                "refusing to push: staged diff matches a credential pattern "
                f"({pattern!r}) — possible secret exfiltration via a committed file"
            )


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
    _assert_no_secrets_in_staged_diff(path)
    _run(["git", "-C", path, "commit", "-m", message])
    sha_result = _run(["git", "-C", path, "rev-parse", "HEAD"])
    sha = sha_result.stdout.strip()
    # Re-auth origin transiently for the push. clone_at_preview_head stripped the
    # token from origin so it was absent during the untrusted Claude run; this
    # step runs afterwards in the orchestrator-controlled finalize job, so
    # restoring the token here does not expose it to the agent.
    _run(["git", "-C", path, "remote", "set-url", "origin", _authed_url(_origin_repo_slug(path))])
    try:
        _run(["git", "-C", path, "push", "origin", "HEAD"])
    except subprocess.CalledProcessError as e:
        raise PushRejectedError(
            f"git push to {path} HEAD failed: {e.stderr or e.stdout or 'unknown'}"
        ) from e
    return sha
