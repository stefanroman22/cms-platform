"""Supabase wrappers for the Solver Agent.

Uses the Postgres function `claim_next_solver_issue(int, int)` for the atomic
priority-ordered claim (the supabase-py client doesn't expose FOR UPDATE
SKIP LOCKED). The function is created via the S3 migration.
"""

from __future__ import annotations

import os
from functools import lru_cache

from supabase import Client, create_client

_MAX_ERROR_LEN = 500
_DEFAULT_MAX_RETRIES = 3
_DEFAULT_STALE_MINUTES = 15


@lru_cache(maxsize=1)
def _supabase() -> Client:
    return create_client(
        os.environ["SUPABASE_URL"],
        os.environ["SUPABASE_SERVICE_ROLE_KEY"],
    )


def _max_retries() -> int:
    return int(os.environ.get("SOLVER_MAX_RETRIES", _DEFAULT_MAX_RETRIES))


def _stale_minutes() -> int:
    return int(os.environ.get("SOLVER_STALE_CLAIM_MINUTES", _DEFAULT_STALE_MINUTES))


def claim_next_issue() -> dict | None:
    """Returns claimed issue row, or None if nothing actionable."""
    sb = _supabase()
    response = sb.rpc(
        "claim_next_solver_issue",
        {
            "p_max_retries": _max_retries(),
            "p_stale_minutes": _stale_minutes(),
        },
    ).execute()
    rows = response.data or []
    return rows[0] if rows else None


def fetch_project(project_id: str) -> dict:
    """Return the full project row for the given project_id."""
    sb = _supabase()
    result = (
        sb.table("projects")
        .select(
            "id, name, slug, github_repo, repo_branch, production_branch, "
            "preview_url, production_url, user_id"
        )
        .eq("id", project_id)
        .single()
        .execute()
    )
    return result.data or {}


def release_issue_failed(issue_id: str, error: str) -> None:
    """Increment retry counter; transition to 'failed' or 'blocked'."""
    sb = _supabase()
    current = (
        sb.table("project_issues").select("agent_retry_count").eq("id", issue_id).single().execute()
    )
    new_count = current.data["agent_retry_count"] + 1
    new_status = "blocked" if new_count >= _max_retries() else "failed"

    sb.table("project_issues").update(
        {
            "agent_status": new_status,
            "agent_claimed_at": None,
            "agent_retry_count": new_count,
            "agent_last_error": error[:_MAX_ERROR_LEN],
        }
    ).eq("id", issue_id).execute()


def mark_done(issue_id: str, *, commit_sha: str) -> None:
    """Clear lock and record the commit SHA. The status='done' transition
    is done by the backend admin endpoint (separate call) because that's
    what fires the S1 Slack notification.
    """
    sb = _supabase()
    sb.table("project_issues").update(
        {
            "agent_commit_sha": commit_sha,
            "agent_status": None,
            "agent_claimed_at": None,
        }
    ).eq("id", issue_id).execute()
