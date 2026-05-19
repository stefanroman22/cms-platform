# Phase 5 — Finalize

**Goal:** Mark issue `status='done'` via backend admin endpoint, persist `agent_commit_sha`, trigger S1 resolved-Slack flow.

**Inputs:** `/tmp/commit_sha`, `/tmp/issue.json`, `CMS_API_TOKEN`, `CMS_BACKEND_URL`.

**Steps:**

**Decision tree (in order):**

1. `/tmp/agent-status.md` exists → `notify_agent_event(kind="rejected", reason=content[:500])` → `release_issue_failed` → exit 0.
2. `CLAUDE_EXIT_CODE != 0` (Claude CLI crashed: OAuth expired, max-turns, internal error) → `notify_agent_event(kind="agent_crashed", reason=f"CLI exit {code}")` → `release_issue_failed` → exit 0.
3. `not has_diff` (agent ran to completion but produced no file changes and no status.md) → `notify_agent_event(kind="no_diff", reason="Agent ran to completion but produced no file changes")` → `release_issue_failed` → exit 0.
4. Otherwise (happy path) → `commit_and_push` → `mark_done` → `trigger_issue_resolved` (3× exp backoff). On final retry failure → `slack.post_thread_event_direct(kind="backend_error", ...)` → exit 0 (the push is durable).
5. On `PushRejectedError` from commit_and_push → `notify_agent_event(kind="backend_error", reason=...)` → write `/tmp/agent-event-emitted` marker → re-raise. `Release on failure` step handles `release_issue_failed` (does not double-emit because of the marker).

Every notify_agent_event call writes `/tmp/agent-event-emitted` on success so `release_issue.py`'s own notify call in `Release on failure` does not duplicate.

**Outputs:** Issue in DB: `status='done'`, `agent_commit_sha=<sha>`, `agent_status=NULL`, `slack_resolved_ts=<from notify>`.

**Failure messages:**
- Backend PATCH 5xx after 3× exp backoff → `slack.post_thread_event_direct` with manual recovery command; commit is durable; exit 0.
- `PushRejectedError` → Slack thread reply posted; `release_issue_failed` called via `Release on failure` step; workflow exits non-zero.
