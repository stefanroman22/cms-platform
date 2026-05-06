"""disable_vercel_auth.py — retrofit per-client Vercel projects.

Walks every Vercel project the configured token can see and disables
Vercel Authentication (ssoProtection) + Password Protection on each
non-infra project. Idempotent: re-running on a project that's already
public is a no-op.

Why: clients click "See Preview" in our CMS dashboard and land on the
deployed Vercel URL. Default Vercel project protection forces them
through a "Request Access" SSO gate. We don't want that — the deployed
preview is meant to be publicly viewable.

Filter: skip any project whose GitHub link points at our monorepo
(stefanroman22/cms-platform) — that covers `roman-technologies` and
`cms-backend-roman` in one rule and survives renames. Belt-and-
suspenders: also skip a project whose name matches the legacy infra
names so a misconfigured project missing its repo link is still safe.

Required env:
    VERCEL_TOKEN   Personal access token from
                   https://vercel.com/account/tokens

Run:
    python scripts/disable_vercel_auth.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.vercel.com"
INFRA_REPO = "stefanroman22/cms-platform"
INFRA_NAMES = {"roman-technologies", "cms-backend-roman"}


def _request(token: str, method: str, path: str, body: dict | None = None) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    data = None
    if body is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(body).encode()
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode() or "{}"
        return json.loads(raw)


def list_all_projects(token: str) -> list[dict]:
    """Pages through /v9/projects and returns every project the token can see."""
    projects: list[dict] = []
    path = "/v9/projects?limit=100"
    while True:
        data = _request(token, "GET", path)
        projects.extend(data.get("projects", []))
        pagination = data.get("pagination") or {}
        next_ts = pagination.get("next")
        if not next_ts:
            return projects
        path = f"/v9/projects?limit=100&until={next_ts}"


def is_infra(project: dict) -> tuple[bool, str]:
    """Returns (skip?, reason). Reason is empty when not skipped."""
    link = project.get("link") or {}
    repo = f"{link.get('org', '')}/{link.get('repo', '')}".strip("/")
    if repo == INFRA_REPO:
        return True, f"linked to monorepo {INFRA_REPO}"
    if project.get("name") in INFRA_NAMES:
        return True, f"name in infra denylist ({project['name']})"
    return False, ""


def disable_protection(token: str, project_id: str) -> None:
    _request(
        token,
        "PATCH",
        f"/v9/projects/{project_id}",
        {"ssoProtection": None, "passwordProtection": None},
    )


def main() -> int:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print(
            "error: VERCEL_TOKEN not set.\n"
            "       export it from https://vercel.com/account/tokens, then re-run.",
            file=sys.stderr,
        )
        return 1

    print("\n🔓 Disabling Vercel deployment protection\n")

    try:
        projects = list_all_projects(token)
    except urllib.error.HTTPError as e:
        body = e.read().decode()
        print(f"error: failed to list projects: {e.code} {body}", file=sys.stderr)
        return 1

    skipped = 0
    patched = 0
    errors = 0

    for proj in projects:
        name = proj.get("name", "<no name>")
        skip, reason = is_infra(proj)
        if skip:
            print(f"  - skip {name} ({reason})")
            skipped += 1
            continue
        try:
            disable_protection(token, proj["id"])
            print(f"  ✓ {name} protection disabled")
            patched += 1
        except urllib.error.HTTPError as e:
            err_body = e.read().decode()
            print(
                f"  ✗ {name} ({proj['id']}): {e.code} {err_body[:200]}",
                file=sys.stderr,
            )
            errors += 1

    print(f"\nDone. {skipped} skipped, {patched} patched, {errors} errors.")
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
