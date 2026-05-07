-- backend/migrations/2026_05_07_project_requests_rls.sql
-- INFRA-006 — Lock down project_requests at the RLS layer.
--
-- The application currently filters by user_id everywhere it reads this
-- table, but the table itself has RLS off. If a future endpoint adds a
-- raw SELECT through the anon client (or a typo'd `.eq("user_id", ...)`
-- gets dropped during a refactor), every client's project request
-- description leaks. Enable RLS now and define explicit policies so the
-- failure mode is "empty result" instead of "everyone's data".
--
-- The service-role key bypasses RLS by design — the backend continues
-- to use it for admin reads. The anon key (used by the public site or
-- any future RLS-bound query) gets zero rows unless one of the two
-- policies below grants access.

ALTER TABLE project_requests ENABLE ROW LEVEL SECURITY;

-- Explicit deny by default: any policy below must affirmatively grant.
-- Postgres semantics: with RLS enabled and zero matching policies, the
-- result is empty. We add policies for the two legitimate read paths.

-- Owner can read their own requests via auth.uid() (Supabase JWT).
DROP POLICY IF EXISTS "owner_can_read_own_requests" ON project_requests;
CREATE POLICY "owner_can_read_own_requests"
  ON project_requests
  FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

-- Owner can insert a request only for themselves.
DROP POLICY IF EXISTS "owner_can_insert_own_request" ON project_requests;
CREATE POLICY "owner_can_insert_own_request"
  ON project_requests
  FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

-- No update / delete policies on purpose. Mutations go through the
-- backend admin path (service-role, bypasses RLS) so they're auditable.
