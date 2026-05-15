-- 2026_05_15 — Slack inbound S1.5 schema
-- Adds columns + idempotency table needed for /slack/events approval +
-- revision flows. Also fixes stale repo_branch data from S1's default.
-- RLS: project_issues + projects use existing tenant policies; slack_processed_events
-- is server-internal (no client access) so RLS stays off but we restrict via no
-- public grants (Supabase service-role-only by default).

-- 1. project_issues: track Slack message ts + revision feedback
ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS slack_resolved_ts TEXT NULL,
  ADD COLUMN IF NOT EXISTS revision_feedback TEXT NULL,
  ADD COLUMN IF NOT EXISTS revision_feedback_at TIMESTAMPTZ NULL;

COMMENT ON COLUMN project_issues.slack_resolved_ts IS
  'Slack message ts of the most recent "Issue Resolved" post. Lookup key for reaction + thread-reply events.';
COMMENT ON COLUMN project_issues.revision_feedback IS
  'Stefan''s last rejection text. Cleared when ✅ approves.';

-- 2. projects: production branch name for fast-forward
ALTER TABLE projects
  ADD COLUMN IF NOT EXISTS production_branch TEXT NOT NULL DEFAULT 'master';

COMMENT ON COLUMN projects.production_branch IS
  'Production git branch. Backend fast-forwards this ref to repo_branch HEAD on ✅ approval.';

-- 3. Data fix: real client repos use cms-preview, not the speculative dev default
UPDATE projects
  SET repo_branch = 'cms-preview'
  WHERE repo_branch = 'dev'
    AND github_repo IS NOT NULL;

-- 4. Idempotency table for Slack event de-dup
CREATE TABLE IF NOT EXISTS slack_processed_events (
  event_id TEXT PRIMARY KEY,
  received_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_slack_processed_events_received_at
  ON slack_processed_events (received_at);
