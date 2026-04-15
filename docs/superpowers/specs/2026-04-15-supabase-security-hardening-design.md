# Supabase Security Hardening — Design Spec

**Date:** 2026-04-15
**Approach:** A — Deny-by-default RLS

---

## Goal

Lock down the Supabase project (`xeluydwpgiddbamysgyu`) so that only the backend service role can access data. Fix every security linter ERROR and the top three WARNs. Do not change application code. Verify login and CMS editing still work end-to-end after every change.

## Architecture context

- **Backend (FastAPI `auth_service`)** uses `SUPABASE_SERVICE_ROLE_KEY` for every Supabase call. The service role bypasses RLS.
- **Frontend (Next.js)** never talks to Supabase directly. All data flows: browser → Next.js API proxy (`/api/[...path]`) → FastAPI → Supabase.
- **Public storage bucket `cms-files`** is read via direct object URLs (`/storage/v1/object/public/cms-files/...`) embedded in website markup. Object URLs bypass RLS; only the "list objects" operation requires the broad SELECT policy that will be removed.
- **Supabase Auth** (`auth.users` schema) is used only for password storage via `crypt()`. JWTs are issued by the custom FastAPI auth service (RS256, argon2id for `public.users.password_hash`).

Implication: enabling RLS with no policies on public tables breaks nothing because no caller (backend or frontend) uses the anon/authenticated role against these tables.

## In scope — 6 work items

### 1. Enable RLS on all 9 public tables with no policies

Tables:
- `users`
- `projects`
- `refresh_tokens`
- `project_services`
- `content_entries`
- `project_issues`
- `email_configs`
- `service_types`
- `project_requests`

Single SQL per table:
```sql
ALTER TABLE public.<table_name> ENABLE ROW LEVEL SECURITY;
```

No `CREATE POLICY` statements. Absence of policies on an RLS-enabled table means the anon and authenticated roles get zero rows. Service role still has full access.

### 2. Harden `update_updated_at` function search_path

```sql
CREATE OR REPLACE FUNCTION public.update_updated_at()
RETURNS TRIGGER
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$;
```

The body references no unqualified identifiers, so pinning `search_path = ''` is safe. This closes the linter's `function_search_path_mutable` warning.

### 3. Remove broad SELECT policy on `cms-files` bucket

The existing policy `"cms-files public read"` grants `SELECT` on all `storage.objects` rows where `bucket_id = 'cms-files'`. This policy is required for *listing* files (PostgREST `/storage/v1/object/list`) but not for direct object URL access, which goes through a signed endpoint that checks bucket-level public visibility, not RLS.

Drop the policy:
```sql
DROP POLICY IF EXISTS "cms-files public read" ON storage.objects;
```

Leave the bucket `public = true` so object URLs remain accessible.

Verification: after drop, `GET /storage/v1/object/public/cms-files/<known-path>` must still return 200.

### 4. Enable leaked-password protection in Supabase Auth

This is a dashboard toggle, not SQL. Must be enabled via Supabase dashboard → Authentication → Policies → "Check passwords against HaveIBeenPwned". Document as a manual step in the plan since the MCP tools don't expose this.

### 5. Verify password policy on all entry points

Known code paths that set a password:
- `POST /auth/change-password` — already enforces `len(new_password) >= 8` (line 116–117 of `routers/auth.py`)
- `POST /admin/clients` — generates a random 16-char password (safe by construction)
- No public signup endpoint exists; accounts are provisioned only by the admin client-creation flow

Action: audit `backend/auth_service/routers/` for any other password-handling endpoints. If found, add the same `len >= 8` check. If none found, document that password-setting is already locked down.

### 6. End-to-end verification (after every change)

Run these checks in order, in a script or manually:

**V1. Admin login still works:**
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"stefanromanpers@gmail.com","password":"<known>"}' \
  -w "\nHTTP_STATUS:%{http_code}"
```
Expected: 200, JSON body with `access_token`.

**V2. Client login still works:**
```bash
curl -s -X POST http://localhost:8001/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"d_laurian@yahoo.com","password":"1234"}' \
  -w "\nHTTP_STATUS:%{http_code}"
```
Expected: 200.

**V3. CMS content save round-trip:**
Manually: open dashboard → pick a service → edit a field → Save. Expect success banner and reload to reflect the change.

**V4. Direct anon-key access is blocked:**
```bash
curl -s "https://xeluydwpgiddbamysgyu.supabase.co/rest/v1/users?select=id" \
  -H "apikey: $ANON_KEY" \
  -H "Authorization: Bearer $ANON_KEY"
```
Expected: empty array `[]` (RLS silently filters all rows). Repeat for `projects`, `project_issues`, `content_entries`, `email_configs`. All must return `[]`.

**V5. Public image URL still works:**
```bash
curl -s -o /dev/null -w "%{http_code}" \
  "https://xeluydwpgiddbamysgyu.supabase.co/storage/v1/object/public/cms-files/<known-file-path>"
```
Expected: 200.

## Out of scope

- No FastAPI code changes.
- No frontend code changes.
- No changes to argon2 / JWT / refresh-token logic — already secure.
- No new RLS policies for future direct-client access — can be added later if the architecture changes.
- No migration of `projects.api_key` column (it's protected by RLS once enabled; rotating is a separate concern).

## Acceptance criteria

- `mcp__supabase__get_advisors(security)` returns **0 ERRORs**.
- `function_search_path_mutable` and `public_bucket_allows_listing` WARNs are cleared.
- `auth_leaked_password_protection` WARN is cleared (dashboard toggle).
- V1–V5 verification steps all pass.

## Risk register

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| RLS on `refresh_tokens` breaks login | Very low | Backend uses service role; service role bypasses RLS. Still — verify V1/V2 after enabling RLS on this table specifically. |
| Dropping `cms-files` SELECT policy breaks hero images on portfolio website | Low | Object URLs don't use RLS; but still — verify V5 after the drop. |
| `SET search_path = ''` on `update_updated_at` breaks trigger | Very low | Function body uses no unqualified identifiers. Verify by editing a service after the change (triggers `updated_at`). |
| HIBP check rejects existing-password change | Very low | Only affects new passwords set after the toggle. Existing users unaffected. |
