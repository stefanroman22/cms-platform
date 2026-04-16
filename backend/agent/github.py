"""GitHub REST API helpers - stdlib only."""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.request import urlopen

API_BASE = "https://api.github.com"


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urlopen(req) as resp:
        raw = resp.read().decode() or "{}"
        return json.loads(raw)


def branch_exists(token: str, github_repo: str, branch: str) -> bool:
    try:
        _request(token, "GET", f"/repos/{github_repo}/git/ref/heads/{branch}")
        return True
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return False
        raise


def create_branch(token: str, github_repo: str, new_branch: str, from_branch: str = "main") -> None:
    """Creates `new_branch` from the tip of `from_branch`. No-op if branch already exists."""
    if branch_exists(token, github_repo, new_branch):
        return

    main_ref = _request(token, "GET", f"/repos/{github_repo}/git/ref/heads/{from_branch}")
    sha = main_ref["object"]["sha"]

    _request(
        token,
        "POST",
        f"/repos/{github_repo}/git/refs",
        {"ref": f"refs/heads/{new_branch}", "sha": sha},
    )
