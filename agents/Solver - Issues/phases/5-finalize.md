# Phase 5 — Finalize

**Goal:** Mark issue `status='done'` via backend admin endpoint, persist `agent_commit_sha`, trigger S1 resolved-Slack flow.

**Inputs:** `/tmp/commit_sha`, `/tmp/issue.json`, `CMS_API_TOKEN`, `CMS_BACKEND_URL`.

**Steps:**
1. Write `agent_commit_sha = <sha>` and `agent_status = NULL` via Supabase (clears lock).
2. PATCH `<backend>/admin/issues/<issue_id>/status` with `{"status": "done"}` and bearer auth.
3. Backend's admin handler fires `slack_notify.notify_issue_resolved` → posts "✅ Issue Resolved" to `#issues-websites` → persists `slack_resolved_ts` → S1.5 awaits Stefan's ✅.

**Outputs:** Issue in DB: `status='done'`, `agent_commit_sha=<sha>`, `agent_status=NULL`, `slack_resolved_ts=<from notify>`.

**Failure messages:**
- Backend PATCH 5xx → log; do NOT mark failed (commit is durable). Stefan can manually flip the status from the dashboard, which fires S1 the normal way.
