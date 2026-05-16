"""Workflow entrypoint on `failure()` — increment retry counter for the
currently-claimed issue.

Reads issue id from /tmp/issue.json (claim_issue.py wrote it). If the
file doesn't exist, no issue was claimed → nothing to release.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import db
import slack as slack_client

logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"


def main() -> int:
    path = Path(ISSUE_JSON_PATH)
    if not path.exists():
        print("no claim to release")
        return 0

    issue = json.loads(path.read_text())
    error = _failure_reason()

    db.release_issue_failed(issue["id"], error)
    print(f"released issue {issue['id']} as failed: {error[:80]}")

    new_count = _current_retry_count(issue["id"])
    max_retries = int(os.environ.get("SOLVER_MAX_RETRIES", "3"))
    if new_count >= max_retries:
        project = issue.get("project", {}) or {}
        slack_client.post_blocked_notification(
            issue_id=issue["id"],
            title=issue["title"],
            project_name=project.get("name") or project.get("slug", "unknown"),
            retry_count=new_count,
            last_error=error,
        )

    return 0


def _failure_reason() -> str:
    """Best-effort: read a step hint from FAILED_STEP env (set by caller workflow,
    if any). Falls back to generic message.
    """
    failed_step = os.environ.get("FAILED_STEP", "")
    if failed_step:
        return f"workflow step failed: {failed_step}"
    return "workflow failure (no specific step recorded)"


def _current_retry_count(issue_id: str) -> int:
    sb = db._supabase()
    row = (
        sb.table("project_issues").select("agent_retry_count").eq("id", issue_id).single().execute()
    )
    return row.data["agent_retry_count"]


if __name__ == "__main__":
    sys.exit(main())
