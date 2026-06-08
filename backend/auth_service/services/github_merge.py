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

    If `base_branch` is protected and refuses the direct ref update (a
    require-pull-request rule), the promotion automatically falls back to
    opening and merging a PR pinned to the same commit, so branch protection is
    respected rather than fatal. Returns a {"object": {"sha": ...}} dict for the
    resulting production SHA. Raises GitHubError on a genuine non-fast-forward
    divergence or any other non-2xx.
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
            # GitHub returns 422 for two very different reasons. A genuine
            # non-fast-forward says so ("Update is not a fast forward") — that's
            # a real divergence the operator must resolve. Anything else (most
            # commonly "Changes must be made through a pull request" on a
            # protected branch) means the direct ref update is forbidden, not
            # that the branches diverged — so promote through a PR instead of
            # giving up with a misleading message.
            if "fast forward" in body_text.lower():
                raise GitHubError(
                    f"Cannot fast-forward {base_branch} to {head_branch} — diverged. "
                    f"Resolve manually. ({body_text})"
                ) from e
            return _promote_via_pull_request(
                repo=repo, base_branch=base_branch, new_sha=new_sha, token=token
            )
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


def _promote_via_pull_request(*, repo: str, base_branch: str, new_sha: str, token: str) -> dict:
    """Promote `new_sha` onto a protected `base_branch` that refuses direct ref
    updates. Opens a PR from a throwaway branch pinned at `new_sha` and merges it
    via the API, so the promotion still lands exactly the approved commit
    (matching the direct-fast-forward path's guarantee) while respecting branch
    protection. Returns the same {"object": {"sha": ...}} shape as fast_forward.
    """
    temp_branch = f"cms-promote-{new_sha[:12]}"
    _create_or_update_ref(repo, temp_branch, new_sha, token)
    try:
        try:
            pr = _api(
                "POST",
                f"{_GH_API}/repos/{repo}/pulls",
                token,
                {
                    "title": f"Promote {temp_branch} → {base_branch}",
                    "head": temp_branch,
                    "base": base_branch,
                    "body": (
                        "Automated production promotion. The base branch is protected, "
                        "so the approved commit is promoted through a pull request "
                        "instead of a direct fast-forward."
                    ),
                },
            )
            merge = _api(
                "PUT",
                f"{_GH_API}/repos/{repo}/pulls/{pr['number']}/merge",
                token,
                {"merge_method": "merge", "sha": new_sha},
            )
        except urllib.error.HTTPError as e:
            raise GitHubError(
                f"GitHub {e.code} promoting via pull request: "
                f"{e.read().decode(errors='replace')}"
            ) from e
    finally:
        # Best-effort cleanup. A leftover branch is harmless and is recovered
        # from on the next attempt (see _create_or_update_ref).
        try:
            _api("DELETE", f"{_GH_API}/repos/{repo}/git/refs/heads/{temp_branch}", token)
        except urllib.error.HTTPError:
            pass
    return {"object": {"sha": merge.get("sha", new_sha)}}


def _create_or_update_ref(repo: str, branch: str, sha: str, token: str) -> None:
    """Create refs/heads/{branch} at `sha`; if it already exists (a prior run's
    cleanup failed), reset it to `sha` so promotion is never permanently wedged
    by a leftover branch."""
    try:
        _api(
            "POST",
            f"{_GH_API}/repos/{repo}/git/refs",
            token,
            {"ref": f"refs/heads/{branch}", "sha": sha},
        )
    except urllib.error.HTTPError as e:
        if e.code != 422:
            raise GitHubError(
                f"GitHub {e.code} creating promotion branch: "
                f"{e.read().decode(errors='replace')}"
            ) from e
        _api(
            "PATCH",
            f"{_GH_API}/repos/{repo}/git/refs/heads/{branch}",
            token,
            {"sha": sha, "force": True},
        )


def _api(method: str, url: str, token: str, payload: dict | None = None) -> dict:
    data = json.dumps(payload).encode() if payload is not None else None
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "User-Agent": "cms-backend/1.0",
    }
    if data is not None:
        headers["Content-Type"] = "application/json"
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=10) as resp:
        raw = resp.read().decode()
        return json.loads(raw) if raw else {}
