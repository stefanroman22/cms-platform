"""Vercel REST API helpers for the agent.

Stdlib-only HTTP (matches scan.py). All functions raise
RuntimeError on unexpected status codes so callers can log + retry.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request
from urllib.request import urlopen

API_BASE = "https://api.vercel.com"


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urlopen(req) as resp:
            raw = resp.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        err_body = e.read().decode()
        raise RuntimeError(f"Vercel API {method} {path} failed: {e.code} {err_body}") from e


def find_project_by_repo(token: str, github_repo: str) -> dict | None:
    """Returns {"id": str, "production_branch": str | None} for the Vercel
    project linked to the given GitHub repo (owner/name), or None.

    Vercel's /v9/projects returns the link as {type, org, repo, productionBranch},
    where `org` is the GitHub owner and `repo` is just the repo name (no slash).
    We compare against `f"{org}/{repo}"` to match against the fully-qualified
    OWNER/NAME slug the caller passes in.
    """
    data = _request(token, "GET", "/v9/projects?limit=100")
    for proj in data.get("projects", []):
        link = proj.get("link") or {}
        if link.get("type") != "github":
            continue
        full = f"{link.get('org', '')}/{link.get('repo', '')}"
        if full == github_repo:
            return {
                "id": proj["id"],
                "production_branch": link.get("productionBranch"),
            }
    return None


def create_project(token: str, name: str, github_repo: str, framework: str | None = None) -> str:
    """Creates a new Vercel project linked to a GitHub repo. Returns project id."""
    payload: dict = {
        "name": name,
        "gitRepository": {
            "type": "github",
            "repo": github_repo,
        },
    }
    if framework:
        payload["framework"] = framework

    data = _request(token, "POST", "/v11/projects", payload)
    return data["id"]


def set_env_var(
    token: str,
    project_id: str,
    key: str,
    value: str,
    target: list[str],
    type_: str = "encrypted",
) -> None:
    """Upserts a Vercel env var on the given environment(s).

    `target` is a subset of: ["production", "preview", "development"].
    """
    # Find existing env var (same key + target)
    existing = _request(token, "GET", f"/v9/projects/{project_id}/env")
    for env in existing.get("envs", []):
        if env.get("key") == key and set(env.get("target") or []) == set(target):
            _request(
                token,
                "PATCH",
                f"/v9/projects/{project_id}/env/{env['id']}",
                {"value": value},
            )
            return

    _request(
        token,
        "POST",
        f"/v9/projects/{project_id}/env",
        {"key": key, "value": value, "type": type_, "target": target},
    )


def trigger_deployment(
    token: str,
    project_id: str,
    github_repo: str,
    branch: str,
    production_branch: str | None = None,
    alias_poll_seconds: int = 30,
) -> dict:
    """Triggers a deployment of `branch` for the Vercel project.

    If `branch == production_branch`, targets production; otherwise preview.
    When production_branch is None, treats any non-'main' branch as preview
    (legacy behaviour; callers should pass the real production branch).

    After creation, polls the deployment object for up to ~alias_poll_seconds
    to get the stable branch alias (e.g. `project-git-cms-preview-team.vercel.app`).
    The stable alias tracks future builds on the branch; the per-deploy URL
    only works for the specific build and becomes stale on every push.

    Returns {"id": str, "url": str} — url is the stable alias if we got one,
    otherwise the per-deploy URL as a fallback.
    """
    import time

    owner, repo = github_repo.split("/", 1)
    is_production = branch == (production_branch or "main")
    payload: dict = {
        "name": repo,
        "project": project_id,
        "gitSource": {
            "type": "github",
            "org": owner,
            "repo": repo,
            "ref": branch,
        },
    }
    # Only include target when it's "production" — Vercel rejects target: null
    # with "Invalid request: `target` should be string." Preview deploys come
    # from omitting the field entirely.
    if is_production:
        payload["target"] = "production"
    data = _request(token, "POST", "/v13/deployments", payload)
    dep_id = data["id"]
    fallback_url = data.get("url") or ""

    # Poll for alias — Vercel assigns it shortly after build starts.
    deadline = time.monotonic() + alias_poll_seconds
    while time.monotonic() < deadline:
        detail = _request(token, "GET", f"/v13/deployments/{dep_id}")
        aliases = detail.get("alias") or []
        if aliases:
            return {"id": dep_id, "url": aliases[0]}
        time.sleep(1.5)

    return {"id": dep_id, "url": fallback_url}
