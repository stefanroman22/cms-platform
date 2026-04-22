"""
One-shot: create the cms-backend-roman Vercel project linked to the CMS
GitHub repo, set env vars, configure rootDirectory to backend/.

Requires env vars:
  VERCEL_TOKEN
  SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_ROLE_KEY
  RESEND_API_KEY
  JWT_PRIVATE_KEY_B64, JWT_PUBLIC_KEY_B64

Idempotent: if the project already exists, updates env vars and exits.
"""
from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API = "https://api.vercel.com"
PROJECT_NAME = "cms-backend-roman"
GITHUB_REPO = "stefanroman22/cms-platform"
ROOT_DIR = "backend"


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
        "gitRepository": {"type": "github", "repo": GITHUB_REPO},
        "rootDirectory": ROOT_DIR,
    }
    data = _req("POST", "/v11/projects", payload)
    return data["id"]


def _env_vars() -> dict:
    return {
        "ENVIRONMENT":               ("production",                                   ["production"]),
        "SUPABASE_URL":              (os.environ.get("SUPABASE_URL", ""),             ["production"]),
        "SUPABASE_ANON_KEY":         (os.environ.get("SUPABASE_ANON_KEY", ""),        ["production"]),
        "SUPABASE_SERVICE_ROLE_KEY": (os.environ.get("SUPABASE_SERVICE_ROLE_KEY", ""),["production"]),
        "JWT_PRIVATE_KEY_B64":       (os.environ.get("JWT_PRIVATE_KEY_B64", ""),      ["production"]),
        "JWT_PUBLIC_KEY_B64":        (os.environ.get("JWT_PUBLIC_KEY_B64", ""),       ["production"]),
        "JWT_ALGORITHM":             ("RS256",                                        ["production"]),
        "RESEND_API_KEY":            (os.environ.get("RESEND_API_KEY", ""),           ["production"]),
        "FRONTEND_ORIGINS":          ("https://cms-frontend-roman.vercel.app",        ["production"]),
    }


def upsert_env_var(project_id: str, key: str, value: str, target: list[str]) -> None:
    existing = _req("GET", f"/v9/projects/{project_id}/env")
    match = next(
        (e for e in existing.get("envs", [])
         if e.get("key") == key and set(e.get("target") or []) == set(target)),
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
    required = ("VERCEL_TOKEN", "SUPABASE_URL", "SUPABASE_ANON_KEY",
                "SUPABASE_SERVICE_ROLE_KEY", "JWT_PRIVATE_KEY_B64",
                "JWT_PUBLIC_KEY_B64", "RESEND_API_KEY")
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        print(f"ERROR: missing env vars: {', '.join(missing)}", file=sys.stderr)
        sys.exit(1)

    existing = find_project(PROJECT_NAME)
    if existing:
        project_id = existing["id"]
        print(f"Found existing project {PROJECT_NAME} ({project_id})")
    else:
        project_id = create_project()
        print(f"Created project {PROJECT_NAME} ({project_id})")

    for key, (value, target) in _env_vars().items():
        upsert_env_var(project_id, key, value, target)

    print(f"\nDone. Project id: {project_id}")


if __name__ == "__main__":
    main()
