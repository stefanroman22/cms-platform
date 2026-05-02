"""
One-shot: create cms-frontend-roman Vercel project linked to the CMS
GitHub repo, rootDirectory=frontend, framework Next.js. Sets FASTAPI_URL
to the backend Vercel URL.

Requires env vars:
  VERCEL_TOKEN

Idempotent.
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.vercel.com"
PROJECT_NAME = "cms-frontend-roman"
GITHUB_REPO = "stefanroman22/cms-platform"
ROOT_DIR = "frontend"
BACKEND_URL = "https://cms-backend-roman.vercel.app"


def _req(method: str, path: str, body: dict | None = None) -> dict:
    token = os.environ["VERCEL_TOKEN"]
    url = f"{API}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req) as r:
            raw = r.read().decode() or "{}"
            return json.loads(raw)
    except urllib.error.HTTPError as e:
        print(f"Vercel {method} {path} failed: {e.code}\n{e.read().decode()}", file=sys.stderr)
        raise


def find_project(name: str) -> dict | None:
    data = _req("GET", "/v9/projects?limit=100")
    for p in data.get("projects", []):
        if p.get("name") == name:
            return p
    return None


def create_project() -> str:
    payload = {
        "name": PROJECT_NAME,
        "framework": "nextjs",
        "gitRepository": {"type": "github", "repo": GITHUB_REPO},
        "rootDirectory": ROOT_DIR,
    }
    data = _req("POST", "/v11/projects", payload)
    return data["id"]


def upsert_env_var(project_id: str, key: str, value: str, target: list[str]) -> None:
    existing = _req("GET", f"/v9/projects/{project_id}/env")
    match = next(
        (
            e
            for e in existing.get("envs", [])
            if e.get("key") == key and set(e.get("target") or []) == set(target)
        ),
        None,
    )
    body = {"key": key, "value": value, "type": "encrypted", "target": target}
    if match:
        _req("PATCH", f"/v9/projects/{project_id}/env/{match['id']}", body)
        print(f"  updated {key} {target}")
    else:
        _req("POST", f"/v9/projects/{project_id}/env", body)
        print(f"  created {key} {target}")


def main() -> None:
    if not os.environ.get("VERCEL_TOKEN"):
        print("ERROR: VERCEL_TOKEN is required", file=sys.stderr)
        sys.exit(1)
    existing = find_project(PROJECT_NAME)
    if existing:
        project_id = existing["id"]
        print(f"Found existing project {PROJECT_NAME} ({project_id})")
    else:
        project_id = create_project()
        print(f"Created project {PROJECT_NAME} ({project_id})")

    upsert_env_var(project_id, "FASTAPI_URL", BACKEND_URL, ["production", "preview"])

    print(f"\nDone. Project id: {project_id}")


if __name__ == "__main__":
    main()
