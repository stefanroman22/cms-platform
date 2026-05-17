"""Trigger the Solver Agent workflow on demand via repository_dispatch.

Primary use: backend fires this immediately after a client submits a new
issue so the Solver Agent runs within ~30s instead of waiting up to an
hour for the next cron tick. The cron schedule remains as a safety net
for failed dispatches and retries.

Uses urllib.request (stdlib) to match services/github_merge.py.
Failures are surfaced via SolverDispatchError; callers must catch and
swallow so that issue creation never fails because of dispatch trouble.
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.request

_GH_API = "https://api.github.com"
_DISPATCH_TIMEOUT_S = 5
_DISPATCH_EVENT_TYPE = "solver-tick"


class SolverDispatchError(Exception):
    pass


def dispatch_solver_tick(*, issue_id: str | None = None) -> None:
    """POST a repository_dispatch event to trigger solver-agent.yml.

    Reads SOLVER_DISPATCH_TOKEN + SOLVER_DISPATCH_REPO from the
    environment so tests can override via monkeypatch. Falls back to
    GITHUB_TOKEN (used elsewhere for S1.5 fast-forward) so a single
    classic PAT with `repo` + `workflow` scopes can serve both flows
    without provisioning a second secret.

    Raises SolverDispatchError on any failure (missing token, non-2xx,
    timeout). Caller is responsible for catching + logging.
    """
    token = os.environ.get("SOLVER_DISPATCH_TOKEN") or os.environ.get("GITHUB_TOKEN", "")
    if not token:
        raise SolverDispatchError("Neither SOLVER_DISPATCH_TOKEN nor GITHUB_TOKEN configured")

    repo = os.environ.get("SOLVER_DISPATCH_REPO", "stefanroman22/cms-platform")

    payload: dict = {"event_type": _DISPATCH_EVENT_TYPE}
    if issue_id is not None:
        payload["client_payload"] = {"issue_id": issue_id, "trigger": "issue_created"}

    body = json.dumps(payload).encode()
    req = urllib.request.Request(
        f"{_GH_API}/repos/{repo}/dispatches",
        data=body,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": "application/vnd.github+json",
            "Content-Type": "application/json",
            "User-Agent": "cms-backend/1.0",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=_DISPATCH_TIMEOUT_S) as resp:
            # GitHub returns 204 No Content on success; any 2xx is fine.
            if not (200 <= resp.status < 300):
                raise SolverDispatchError(
                    f"GitHub {resp.status} on dispatch: {resp.read().decode(errors='replace')}"
                )
    except urllib.error.HTTPError as e:
        body_text = e.read().decode(errors="replace")
        raise SolverDispatchError(f"GitHub {e.code} on dispatch: {body_text}") from e
    except urllib.error.URLError as e:
        raise SolverDispatchError(f"Network error on dispatch: {e.reason}") from e
    except TimeoutError as e:
        raise SolverDispatchError("Timeout on dispatch") from e
