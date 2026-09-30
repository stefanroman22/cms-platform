"""prune_vercel_previews.py — keep Vercel Function Storage under the free tier.

Vercel Hobby keeps every deployment forever, and each one stores its
function bundles. That cumulative size is the "Function Storage" metric
that fills up the 10 GB free tier. This script prunes the ones we don't
need while keeping everything that matters:

  KEEP  every production deployment (target == "production") — live sites
        and full rollback history are never touched.
  KEEP  the newest preview per (project, git branch) — that's the URL you
        open to check a `dev` / feature push (…-git-<branch>-…vercel.app
        always points at it).
  DELETE every older preview.

In-progress deployments (BUILDING / QUEUED / INITIALIZING) are left alone.

Required env:
    VERCEL_TOKEN     Personal/team access token from
                     https://vercel.com/account/tokens
Optional env:
    VERCEL_TEAM_ID   Team scope (default: the cms/clients team below).
    PRUNE_DRY_RUN    "1"/"true" => list what would be deleted, delete nothing.

Run:
    python scripts/prune_vercel_previews.py
"""

from __future__ import annotations

import json
import os
import sys
import urllib.error
import urllib.request

API_BASE = "https://api.vercel.com"
DEFAULT_TEAM_ID = "team_tG5MNAl15KS2zPlAvmZJTl9y"
# States that are safe to delete. In-progress ones can't be deleted and
# might be the build you're waiting on, so we skip them.
DELETABLE_STATES = {"READY", "ERROR", "CANCELED"}


def _request(token: str, method: str, path: str) -> dict:
    url = f"{API_BASE}{path}"
    headers = {"Authorization": f"Bearer {token}"}
    req = urllib.request.Request(url, headers=headers, method=method)
    with urllib.request.urlopen(req) as resp:
        raw = resp.read().decode() or "{}"
        return json.loads(raw)


def list_all_deployments(token: str, team_id: str) -> list[dict]:
    """Pages through /v6/deployments and returns every deployment in scope."""
    deployments: list[dict] = []
    base = f"/v6/deployments?limit=100&teamId={team_id}"
    path = base
    while True:
        data = _request(token, "GET", path)
        batch = data.get("deployments", [])
        deployments.extend(batch)
        pagination = data.get("pagination") or {}
        next_ts = pagination.get("next")
        if not next_ts or not batch:
            return deployments
        path = f"{base}&until={next_ts}"


def _target(dep: dict) -> str:
    # Older payloads use `target`; some use `meta.target`. Production is the
    # only value we treat as "keep always".
    return dep.get("target") or (dep.get("meta") or {}).get("target") or ""


def _branch(dep: dict) -> str:
    return (dep.get("meta") or {}).get("githubCommitRef", "")


def _project(dep: dict) -> str:
    return dep.get("name", "")


def _created(dep: dict) -> int:
    return dep.get("created") or dep.get("createdAt") or 0


def select_for_deletion(deployments: list[dict]) -> tuple[list[dict], dict]:
    """Returns (to_delete, kept_latest_per_branch_by_group)."""
    previews_by_group: dict[tuple[str, str], list[dict]] = {}
    for dep in deployments:
        if _target(dep) == "production":
            continue  # keep all production
        group = (_project(dep), _branch(dep))
        previews_by_group.setdefault(group, []).append(dep)

    to_delete: list[dict] = []
    kept: dict[tuple[str, str], dict] = {}
    for group, deps in previews_by_group.items():
        deps.sort(key=_created, reverse=True)  # newest first
        kept[group] = deps[0]  # keep newest preview for this branch
        for dep in deps[1:]:
            if dep.get("state") in DELETABLE_STATES:
                to_delete.append(dep)
    return to_delete, kept


def delete_deployment(token: str, team_id: str, dep_id: str) -> None:
    _request(token, "DELETE", f"/v13/deployments/{dep_id}?teamId={team_id}")


def main() -> int:
    token = os.environ.get("VERCEL_TOKEN")
    if not token:
        print(
            "error: VERCEL_TOKEN not set.\n"
            "       create one at https://vercel.com/account/tokens, then re-run.",
            file=sys.stderr,
        )
        return 1
    team_id = os.environ.get("VERCEL_TEAM_ID", DEFAULT_TEAM_ID)
    dry_run = os.environ.get("PRUNE_DRY_RUN", "").lower() in {"1", "true", "yes"}

    mode = "DRY RUN (no deletions)" if dry_run else "LIVE"
    print(f"\n🧹 Pruning old Vercel previews — {mode}  (team {team_id})\n")

    try:
        deployments = list_all_deployments(token, team_id)
    except urllib.error.HTTPError as e:
        print(f"error: listing deployments failed: {e.code} {e.read().decode()}", file=sys.stderr)
        return 1

    prod = sum(1 for d in deployments if _target(d) == "production")
    to_delete, kept = select_for_deletion(deployments)

    print(f"  total deployments:        {len(deployments)}")
    print(f"  production (always kept):  {prod}")
    print(f"  latest previews kept:      {len(kept)}")
    print(f"  old previews to delete:    {len(to_delete)}\n")

    if not to_delete:
        print("Nothing to prune. ✅")
        return 0

    deleted = 0
    errors = 0
    for dep in to_delete:
        dep_id = dep.get("uid") or dep.get("id")
        label = f"{_project(dep)} [{_branch(dep) or 'no-branch'}] {dep_id}"
        if dry_run:
            print(f"  would delete  {label}")
            continue
        try:
            delete_deployment(token, team_id, dep_id)
            print(f"  ✓ deleted     {label}")
            deleted += 1
        except urllib.error.HTTPError as e:
            print(f"  ✗ failed      {label}: {e.code} {e.read().decode()[:160]}", file=sys.stderr)
            errors += 1

    if dry_run:
        print(f"\nDry run complete. {len(to_delete)} would be deleted.")
        return 0
    print(
        f"\nDone. {deleted} deleted, {errors} errors, {prod} production kept, {len(kept)} latest previews kept."
    )
    return 0 if errors == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
