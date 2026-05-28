"""Fast-forward a base branch to a head branch via GitHub REST API.

Used by S1.5 Slack approval flow: when Stefan ✅ a resolved-issue
message, we promote cms-preview → master on the client repo, which
triggers a Vercel production deploy.

Uses urllib.request (stdlib) to match the existing services/ pattern;
no new dependencies.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_GH_API = "https://api.github.com"


class GitHubError(Exception):
    pass


def fast_forward(
    *, repo: str, base_branch: str, head_branch: str, target_sha: str | None = None
) -> dict:
    """PATCH `base_branch` ref to point at `target_sha` (if provided) or HEAD of `head_branch`.

    `repo` is "owner/name". When `target_sha` is provided, the GET on
    `head_branch` is skipped — callers use this to pin promotion to a specific
    commit instead of trusting "whatever's on head_branch right now," which
    matters when head_branch may have drifted between solver run and approval.
    Returns the GitHub API JSON response. Raises GitHubError on any non-2xx.
    """
    token = os.environ.get("GITHUB_TOKEN")
    if not token:
        raise GitHubError("GITHUB_TOKEN not configured")

    if target_sha:
        new_sha = target_sha
    else:
        head = _get(f"{_GH_API}/repos/{repo}/git/refs/heads/{head_branch}", token)
        new_sha = head["object"]["sha"]

    body = json.dumps({"sha": new_sha, "force": False}).encode()
    req = urllib.request.Request(
        f"{_GH_API}/repos/{repo}/git/refs/heads/{base_branch}",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cms-backend/1.0",
        },
        method="PATCH",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        if e.code == 422:
            raise GitHubError(
                f"Cannot fast-forward {base_branch} to {head_branch} — diverged. "
                f"Resolve manually. ({body_text})"
            ) from e
        raise GitHubError(f"GitHub {e.code}: {body_text}") from e


def _get(url: str, token: str) -> dict:
    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "User-Agent": "cms-backend/1.0",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as e:
        raise GitHubError(f"GitHub {e.code} on {url}: {e.read().decode(errors='replace')}") from e
