"""Workflow entrypoint after the Claude Code action runs.

Decision tree:
- /tmp/agent-status.md exists → release_issue_failed(content), no push
- no diff in working tree → release_issue_failed("no file changes"), no push
- otherwise → commit + push + mark_done + trigger_issue_resolved
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import backend_api
import db
import repo

logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"
STATUS_MD_PATH = "/tmp/agent-status.md"
REPO_DIR = "./client-repo"


def main() -> int:
    issue = json.loads(Path(ISSUE_JSON_PATH).read_text())
    status_md = Path(STATUS_MD_PATH)

    if status_md.exists():
        reason = status_md.read_text().strip()[:500]
        db.release_issue_failed(issue["id"], reason or "agent wrote empty status.md")
        print(f"released as failed: {reason}")
        return 0

    if not repo.has_diff(REPO_DIR):
        db.release_issue_failed(issue["id"], "agent produced no file changes")
        print("released as failed: no diff")
        return 0

    sha = repo.commit_and_push(
        path=REPO_DIR,
        issue_id=issue["id"],
        issue_title=issue["title"],
    )
    print(f"pushed commit {sha[:7]}")

    db.mark_done(issue["id"], commit_sha=sha)

    try:
        backend_api.trigger_issue_resolved(issue["id"])
        print("backend mark-done + Slack notify dispatched")
    except Exception:
        logger.exception("backend trigger_issue_resolved failed (commit is durable)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
