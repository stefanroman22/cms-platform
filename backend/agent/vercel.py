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


def find_project_by_repo(token: str, github_repo: str) -> str | None:
    """Returns the Vercel project id linked to the given GitHub repo, or None."""
    data = _request(token, "GET", "/v9/projects?limit=100")
    for proj in data.get("projects", []):
        link = proj.get("link") or {}
        if link.get("type") == "github" and link.get("repo") == github_repo:
            return proj["id"]
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
) -> dict:
    """Triggers a deployment of `branch` for the Vercel project.

    Returns {"id": str, "url": str} — url is the *.vercel.app hostname.
    """
    owner, repo = github_repo.split("/", 1)
    payload = {
        "name": repo,
        "project": project_id,
        "gitSource": {
            "type": "github",
            "ref": branch,
            "repoId": None,
        },
        "target": "production" if branch == "main" else None,
    }
    data = _request(token, "POST", "/v13/deployments", payload)
    return {"id": data["id"], "url": data.get("url") or ""}
