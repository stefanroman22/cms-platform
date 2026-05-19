"""Workflow entrypoint after the Claude Code action runs.

Decision tree (in order):
1. /tmp/agent-status.md exists                → notify_agent_event(rejected)        → release_failed, exit 0
2. CLAUDE_EXIT_CODE != 0                       → notify_agent_event(agent_crashed)   → release_failed, exit 0
3. no diff in working tree                     → notify_agent_event(no_diff)         → release_failed, exit 0
4. otherwise (happy path)                      → commit_and_push → mark_done →
                                                  trigger_issue_resolved (3× retry) →
                                                  on retry exhaustion: direct Slack fallback
5. PushRejectedError from commit_and_push      → notify_agent_event(backend_error)   → write marker → re-raise

Every notify_agent_event call writes /tmp/agent-event-emitted; release_issue.py
checks for it on the failure path to avoid double-posting.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from pathlib import Path

import backend_api
import db
import repo
import slack as slack_client
from supabase import create_client

logger = logging.getLogger(__name__)

ISSUE_JSON_PATH = "/tmp/issue.json"
STATUS_MD_PATH = "/tmp/agent-status.md"
EVENT_MARKER_PATH = "/tmp/agent-event-emitted"
REPO_DIR = "./client-repo"


def _write_event_marker() -> None:
    """Marker so release_issue.py knows finalize already emitted an event."""
    try:
        Path(EVENT_MARKER_PATH).write_text("1")
    except Exception:
        logger.exception("could not write event marker (continuing)")


def _emit_event(issue_id: str, kind: str, reason: str) -> None:
    backend_api.notify_agent_event(issue_id, kind=kind, reason=reason)
    _write_event_marker()


def _fetch_slack_created_ts(issue_id: str) -> str | None:
    """Direct supabase lookup — used only on the backend-error fallback path
    where the backend admin endpoint itself is the failing target."""
    try:
        sb = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_SERVICE_ROLE_KEY"],
        )
        result = (
            sb.table("project_issues")
            .select("slack_created_ts")
            .eq("id", issue_id)
            .single()
            .execute()
        )
        return (result.data or {}).get("slack_created_ts")
    except Exception:
        logger.exception("could not fetch slack_created_ts for fallback")
        return None


def main() -> int:
    issue = json.loads(Path(ISSUE_JSON_PATH).read_text())
    issue_id = issue["id"]
    status_md = Path(STATUS_MD_PATH)
    claude_exit_code = int(os.environ.get("CLAUDE_EXIT_CODE", "0") or "0")

    # Branch 1: Agent rejected with a written reason.
    if status_md.exists():
        reason = status_md.read_text().strip()[:500] or "agent wrote empty status.md"
        _emit_event(issue_id, kind="rejected", reason=reason)
        db.release_issue_failed(issue_id, reason)
        print(f"released as failed (rejected): {reason}")
        return 0

    # Branch 2: Claude CLI exited non-zero (OAuth, max-turns, internal error).
    if claude_exit_code != 0:
        reason = f"CLI exit {claude_exit_code} — see workflow logs"
        _emit_event(issue_id, kind="agent_crashed", reason=reason)
        db.release_issue_failed(issue_id, reason)
        print(f"released as failed (agent crashed): {reason}")
        return 0

    # Branch 3: No file changes and no status.md (likely agent forgot to write).
    if not repo.has_diff(REPO_DIR):
        reason = (
            "Agent ran to completion but produced no file changes and no status.md "
            "— likely forgot to write a reject reason before exiting"
        )
        _emit_event(issue_id, kind="no_diff", reason=reason)
        db.release_issue_failed(issue_id, "no file changes")
        print("released as failed (no diff)")
        return 0

    # Branch 4 (happy path) or Branch 5 (push rejected).
    try:
        sha = repo.commit_and_push(
            path=REPO_DIR,
            issue_id=issue_id,
            issue_title=issue["title"],
        )
    except repo.PushRejectedError as e:
        reason = (
            f"cms-preview moved during run; local commit lost (runner workspace "
            f"is ephemeral). Re-trigger the workflow after staging stabilizes. "
            f"Detail: {e}"
        )
        _emit_event(issue_id, kind="backend_error", reason=reason)
        # Do NOT release_issue_failed here — let `Release on failure` workflow
        # step do it (via release_issue.py). The event marker we just wrote
        # prevents release_issue.py from double-posting.
        raise

    print(f"pushed commit {sha[:7]}")
    db.mark_done(issue_id, commit_sha=sha)

    # Branch 4 happy path: tell backend, which fires the "✅ Resolved" Slack post.
    try:
        backend_api.trigger_issue_resolved(issue_id)
        print("backend mark-done + Slack notify dispatched")
    except Exception as e:
        # Backend is the failing target — go direct to Slack so the user sees
        # SOMETHING. The push and mark_done already happened, so the work is
        # durable; this is just observability.
        logger.exception("backend trigger_issue_resolved failed after retries")
        thread_ts = _fetch_slack_created_ts(issue_id)
        slack_client.post_thread_event_direct(
            thread_ts=thread_ts,
            kind="backend_error",
            reason=(
                f"Fix pushed (sha {sha[:7]}) but backend mark-done failed: {e}. "
                f"Manual recovery: PATCH /admin/issues/{issue_id}/status with "
                f'{{"status": "done"}}'
            ),
        )
        _write_event_marker()
        # exit 0 — the push is durable; this is observability only.

    return 0


if __name__ == "__main__":
    sys.exit(main())
