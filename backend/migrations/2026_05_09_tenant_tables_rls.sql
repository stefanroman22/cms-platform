-- backend/migrations/2026_05_09_tenant_tables_rls.sql
-- BE-010 — Enable RLS on every tenant-scoped table.
--
-- Backend uses the service-role key everywhere (see services/supabase_client.py:
-- get_supabase_admin), and service-role BYPASSES RLS by design. So enabling RLS
-- here is a no-op for current code paths.
--
-- The value is in the failure mode: any future endpoint that uses the anon
-- client, or a typo'd `.eq("user_id", uid)` that gets dropped during refactor,
-- now returns ZERO rows for cross-tenant data instead of leaking everything.
--
-- Note on auth.uid(): this codebase currently authenticates via a hand-rolled
-- session cookie (`sid` -> services/sessions.py), not Supabase Auth JWTs. So
-- `auth.uid()` is NULL for every request that reaches PostgREST today, and the
-- owner policies below reduce to "deny all to anon/authenticated" — exactly
-- the fail-closed posture we want. If a future migration links public.users.id
-- to auth.users.id and the dashboard switches to Supabase Auth JWTs, the same
-- policies become live owner-enforcement with no further changes.
--
-- Tables covered:
--   - users           (per-row owner = id)
--   - sessions        (per-row owner = user_id)
--   - projects        (per-row owner = user_id)
--   - content_entries (per-row owner = projects.user_id via project_services)
--   - project_issues  (per-row owner = projects.user_id via project_id FK)
--
-- `project_requests` already gated by 2026_05_07_project_requests_rls.sql.
-- `admin_api_keys` already has RLS on (no policies = default-deny for anon).

BEGIN;

----------------------------------------------------------------------
-- 1. users
----------------------------------------------------------------------
ALTER TABLE users ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "users_self_select" ON users;
CREATE POLICY "users_self_select"
  ON users
  FOR SELECT
  TO authenticated
  USING (id = auth.uid());

DROP POLICY IF EXISTS "users_self_update" ON users;
CREATE POLICY "users_self_update"
  ON users
  FOR UPDATE
  TO authenticated
  USING (id = auth.uid())
  WITH CHECK (id = auth.uid());

----------------------------------------------------------------------
-- 2. sessions
----------------------------------------------------------------------
ALTER TABLE sessions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "sessions_self_select" ON sessions;
CREATE POLICY "sessions_self_select"
  ON sessions
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

----------------------------------------------------------------------
-- 3. projects
----------------------------------------------------------------------
ALTER TABLE projects ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "projects_owner_select" ON projects;
CREATE POLICY "projects_owner_select"
  ON projects
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

DROP POLICY IF EXISTS "projects_owner_insert" ON projects;
CREATE POLICY "projects_owner_insert"
  ON projects
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "projects_owner_update" ON projects;
CREATE POLICY "projects_owner_update"
  ON projects
  FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- DELETE intentionally absent: project deletion is admin-only via service-role.

----------------------------------------------------------------------
-- 4. content_entries (owner via project_services -> projects FK chain)
--    content_entries.project_service_id -> project_services.id
--    project_services.project_id        -> projects.id
----------------------------------------------------------------------
ALTER TABLE content_entries ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "content_entries_owner_select" ON content_entries;
CREATE POLICY "content_entries_owner_select"
  ON content_entries
  FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM project_services ps
      JOIN projects p ON p.id = ps.project_id
      WHERE ps.id = content_entries.project_service_id
        AND p.user_id = auth.uid()
    )
  );

DROP POLICY IF EXISTS "content_entries_owner_write" ON content_entries;
CREATE POLICY "content_entries_owner_write"
  ON content_entries
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM project_services ps
      JOIN projects p ON p.id = ps.project_id
      WHERE ps.id = content_entries.project_service_id
        AND p.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM project_services ps
      JOIN projects p ON p.id = ps.project_id
      WHERE ps.id = content_entries.project_service_id
        AND p.user_id = auth.uid()
    )
  );

----------------------------------------------------------------------
-- 5. project_issues (owner via projects FK)
----------------------------------------------------------------------
ALTER TABLE project_issues ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "project_issues_owner_all" ON project_issues;
CREATE POLICY "project_issues_owner_all"
  ON project_issues
  FOR ALL
  TO authenticated
  USING (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_issues.project_id
        AND p.user_id = auth.uid()
    )
  )
  WITH CHECK (
    EXISTS (
      SELECT 1 FROM projects p
      WHERE p.id = project_issues.project_id
        AND p.user_id = auth.uid()
    )
  );

----------------------------------------------------------------------
-- 6. Reporting view for the CI presence test.
--    Service-role can read; anon cannot (default-deny on the underlying
--    pg_tables row in PostgREST exposure).
--    project_requests is included so the CI presence test (Task 1) catches
--    regression on the table covered by 2026_05_07_project_requests_rls.sql.
----------------------------------------------------------------------
DROP VIEW IF EXISTS tenant_rls_status;
CREATE VIEW tenant_rls_status AS
SELECT tablename, rowsecurity
FROM pg_tables
WHERE schemaname = 'public'
  AND tablename IN (
    'users',
    'sessions',
    'projects',
    'content_entries',
    'project_issues',
    'project_requests'
  );

-- service_role only: the CI presence test reads via service-role; granting to
-- `authenticated` would render partial rows (pg_tables filters by privilege)
-- and make the test flake.
GRANT SELECT ON tenant_rls_status TO service_role;

COMMIT;
