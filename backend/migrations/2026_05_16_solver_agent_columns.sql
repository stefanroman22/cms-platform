-- 2026_05_16 — Solver Agent (S3) columns + claim RPC
-- Adds agent-state tracking to project_issues for the GitHub Actions cron
-- worker that auto-fixes client-submitted issues. The atomic claim query uses
-- FOR UPDATE SKIP LOCKED + a 15-min stale-claim window. See
-- docs/superpowers/specs/2026-05-16-solver-agent-s3-design.md for the data model.

ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS agent_status TEXT NULL,
  ADD COLUMN IF NOT EXISTS agent_claimed_at TIMESTAMPTZ NULL,
  ADD COLUMN IF NOT EXISTS agent_retry_count INT NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS agent_last_error TEXT NULL,
  ADD COLUMN IF NOT EXISTS agent_commit_sha TEXT NULL;

COMMENT ON COLUMN project_issues.agent_status IS
  'Solver agent state machine: NULL/idle | claimed | failed | blocked. Separate from user-facing status.';
COMMENT ON COLUMN project_issues.agent_claimed_at IS
  'When the solver claimed this issue. Stale claims (>15 min) are released on the next cron tick.';
COMMENT ON COLUMN project_issues.agent_retry_count IS
  'Count of solver attempts. Reset to 0 when S1.5 stores fresh revision_feedback. Issue blocked at >= SOLVER_MAX_RETRIES (default 3).';
COMMENT ON COLUMN project_issues.agent_last_error IS
  'Short text (<=500 chars) of the last solver failure reason.';
COMMENT ON COLUMN project_issues.agent_commit_sha IS
  'Short SHA of commit the solver pushed to cms-preview. For audit + Slack thread context.';

-- Atomic claim function used by Solver Agent. No arbitrary SQL → no injection surface.
-- Returns at most one row, locks it via FOR UPDATE SKIP LOCKED, sets agent_status='claimed'.
CREATE OR REPLACE FUNCTION claim_next_solver_issue(
  p_max_retries INT DEFAULT 3,
  p_stale_minutes INT DEFAULT 15
)
RETURNS TABLE (
  id UUID,
  project_id UUID,
  title TEXT,
  description TEXT,
  priority TEXT,
  status TEXT,
  revision_feedback TEXT
)
LANGUAGE plpgsql
SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  WITH next_issue AS (
    SELECT pi.id FROM project_issues pi
    WHERE
      (
        (pi.status = 'pending' AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
        OR
        (pi.status = 'in_progress' AND pi.revision_feedback IS NOT NULL AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
      )
      AND pi.agent_retry_count < p_max_retries
      AND COALESCE(pi.agent_status, 'idle') != 'blocked'
      AND (pi.agent_claimed_at IS NULL OR pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    ORDER BY
      CASE pi.priority
        WHEN 'High' THEN 1
        WHEN 'Medium' THEN 2
        WHEN 'Low' THEN 3
        ELSE 4
      END,
      pi.created_at ASC
    LIMIT 1
    FOR UPDATE SKIP LOCKED
  )
  UPDATE project_issues
  SET
    agent_status = 'claimed',
    agent_claimed_at = now()
  WHERE project_issues.id = (SELECT next_issue.id FROM next_issue)
  RETURNING
    project_issues.id, project_issues.project_id, project_issues.title,
    project_issues.description, project_issues.priority, project_issues.status,
    project_issues.revision_feedback;
END;
$$;

REVOKE ALL ON FUNCTION claim_next_solver_issue(INT, INT) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION claim_next_solver_issue(INT, INT) TO service_role;
