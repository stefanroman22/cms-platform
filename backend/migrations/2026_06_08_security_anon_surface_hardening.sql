-- 2026-06-08 — Security: lock down the public anon/authenticated Supabase surface.
--
-- Addresses:
--   * SEC-004  — anon/authenticated/PUBLIC can EXECUTE the SECURITY DEFINER solver-claim
--                RPCs (claim_next_solver_issue, claim_specific_solver_issue) via PostgREST
--                /rest/v1/rpc → cross-tenant issue disclosure + auto-fix queue poisoning DoS.
--   * SEC-013  — slack_processed_events idempotency ledger has RLS disabled with full anon
--                DML grants (readable/writable/truncatable by the public anon key).
--   * advisors — function_search_path_mutable (the claim_* RPCs + the two updated_at trigger
--                functions) and security_definer_view (tenant_rls_status).
--
-- The backend reaches all of these with the service-role key, which BYPASSES RLS and keeps
-- its own grants, so none of the REVOKE/RLS/INVOKER changes below affect the application.
-- The GitHub-Actions Solver calls the claim RPCs with the service-role key as well.

-- ── SEC-004: solver-claim RPCs ───────────────────────────────────────────────
-- Re-create both with a pinned (non-mutable) search_path and schema-qualified table
-- references. CREATE OR REPLACE resets the ACL to the default PUBLIC EXECUTE, so the
-- REVOKE/GRANT below MUST follow. claim_specific_solver_issue had drifted (applied
-- out-of-band, untracked) — it is captured here so repo == live.

create or replace function public.claim_next_solver_issue(
  p_max_retries integer default 3,
  p_stale_minutes integer default 15
)
returns table(id uuid, project_id uuid, title text, description text, priority text, status text, revision_feedback text)
language plpgsql
security definer
set search_path = ''
as $function$
begin
  return query
  with next_issue as (
    select pi.id from public.project_issues pi
    where (
        (pi.status = 'pending' and coalesce(pi.agent_status, 'idle') in ('idle', 'failed'))
        or
        (pi.status = 'in_progress' and pi.revision_feedback is not null and coalesce(pi.agent_status, 'idle') in ('idle', 'failed'))
      )
      and pi.agent_retry_count < p_max_retries
      and coalesce(pi.agent_status, 'idle') != 'blocked'
      and (pi.agent_claimed_at is null or pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    order by
      case pi.priority when 'High' then 1 when 'Medium' then 2 when 'Low' then 3 else 4 end,
      pi.created_at asc
    limit 1
    for update skip locked
  )
  update public.project_issues
  set agent_status = 'claimed', agent_claimed_at = now()
  where public.project_issues.id = (select next_issue.id from next_issue)
  returning
    public.project_issues.id, public.project_issues.project_id, public.project_issues.title,
    public.project_issues.description, public.project_issues.priority, public.project_issues.status,
    public.project_issues.revision_feedback;
end;
$function$;

create or replace function public.claim_specific_solver_issue(
  p_issue_id uuid,
  p_max_retries integer default 3,
  p_stale_minutes integer default 15
)
returns table(id uuid, project_id uuid, title text, description text, priority text, status text, revision_feedback text)
language plpgsql
security definer
set search_path = ''
as $function$
begin
  return query
  with target as (
    select pi.id from public.project_issues pi
    where pi.id = p_issue_id
      and (
        (pi.status = 'pending' and coalesce(pi.agent_status, 'idle') in ('idle', 'failed'))
        or
        (pi.status = 'in_progress' and pi.revision_feedback is not null and coalesce(pi.agent_status, 'idle') in ('idle', 'failed'))
      )
      and pi.agent_retry_count < p_max_retries
      and coalesce(pi.agent_status, 'idle') != 'blocked'
      and (pi.agent_claimed_at is null or pi.agent_claimed_at < now() - (p_stale_minutes || ' minutes')::interval)
    for update skip locked
  )
  update public.project_issues
  set agent_status = 'claimed', agent_claimed_at = now()
  where public.project_issues.id = (select target.id from target)
  returning
    public.project_issues.id, public.project_issues.project_id, public.project_issues.title,
    public.project_issues.description, public.project_issues.priority, public.project_issues.status,
    public.project_issues.revision_feedback;
end;
$function$;

revoke all on function public.claim_next_solver_issue(integer, integer) from public, anon, authenticated;
revoke all on function public.claim_specific_solver_issue(uuid, integer, integer) from public, anon, authenticated;
grant execute on function public.claim_next_solver_issue(integer, integer) to service_role;
grant execute on function public.claim_specific_solver_issue(uuid, integer, integer) to service_role;

-- ── search_path pin on the remaining trigger functions ───────────────────────
alter function public.scrape_jobs_set_updated_at() set search_path = '';
alter function public.leads_set_updated_at() set search_path = '';

-- ── SEC-013: slack_processed_events idempotency ledger ───────────────────────
-- Enable RLS (no policy ⇒ no anon/authenticated access via PostgREST) and revoke the
-- table grants for defense-in-depth. service_role bypasses RLS and keeps its grant.
alter table public.slack_processed_events enable row level security;
revoke all on table public.slack_processed_events from anon, authenticated;

-- ── tenant_rls_status view (security_definer_view advisor) ───────────────────
-- Run with the querying user's privileges, and restrict to service_role (internal
-- RLS-posture check used by CI/ops, not a public endpoint).
alter view public.tenant_rls_status set (security_invoker = true);
revoke all on table public.tenant_rls_status from anon, authenticated;
