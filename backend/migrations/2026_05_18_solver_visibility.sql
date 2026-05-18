-- 2026_05_18 — Solver agent staging-model + visibility pass
-- Adds slack_created_ts (mirrors slack_resolved_ts) for threading agent-event
-- notifications under the original "New Issue" Slack post. Adds the
-- claim_specific_solver_issue RPC so repository_dispatch can target a
-- specific issue instead of running the priority queue.

-- 1. Persist Slack ts of the "New Issue" message for thread replies
ALTER TABLE project_issues
  ADD COLUMN IF NOT EXISTS slack_created_ts TEXT NULL;

COMMENT ON COLUMN project_issues.slack_created_ts IS
  'Slack ts of the "New Issue" top-level post. Lookup key for agent-event thread replies (rejection, no_diff, agent_crashed, backend_error).';

-- 2. Targeted claim RPC (called when repository_dispatch.client_payload.issue_id is set)
CREATE OR REPLACE FUNCTION public.claim_specific_solver_issue(
  p_issue_id uuid,
  p_max_retries integer DEFAULT 3,
  p_stale_minutes integer DEFAULT 15
)
RETURNS TABLE(id uuid, project_id uuid, title text, description text,
              priority text, status text, revision_feedback text)
LANGUAGE plpgsql SECURITY DEFINER
AS $$
BEGIN
  RETURN QUERY
  WITH target AS (
    SELECT pi.id FROM project_issues pi
    WHERE pi.id = p_issue_id
      AND (
        (pi.status = 'pending' AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
        OR
        (pi.status = 'in_progress' AND pi.revision_feedback IS NOT NULL
         AND COALESCE(pi.agent_status, 'idle') IN ('idle', 'failed'))
      )
      AND pi.agent_retry_count < p_max_retries
      AND COALESCE(pi.agent_status, 'idle') != 'blocked'
      AND (pi.agent_claimed_at IS NULL
           OR pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    FOR UPDATE SKIP LOCKED
  )
  UPDATE project_issues
  SET agent_status = 'claimed', agent_claimed_at = now()
  WHERE project_issues.id = (SELECT target.id FROM target)
  RETURNING
    project_issues.id, project_issues.project_id, project_issues.title,
    project_issues.description, project_issues.priority, project_issues.status,
    project_issues.revision_feedback;
END;
$$;
