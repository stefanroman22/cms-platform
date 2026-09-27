# Security runbook

Human procedures, the credential rotation log, the threat model and the incident runbook. The live
findings (and the defenses they verify) are in [`FINDINGS.md`](./FINDINGS.md), maintained by the
Friday review and Saturday fix routines. Those routines do not read or write this file.
**Never delete rotation-log entries:** they are the audit trail when a leak is suspected.

## Rotation log

| Date | What was rotated | Why | Operator |
|------|------------------|-----|----------|
| 2026-04-30 | Supabase legacy JWT secret (rolls both `anon` and `service_role`) | Old keys were committed in `backend/auth_service/.env.example` and visible in git history | Stefan | <!-- docs-check: ignore -->
| 2026-04-30 | Supabase database password | Old password was embedded in `SUPABASE_DB_URL` in committed `.env.example` files | Stefan |
| 2026-04-30 | Resend API key (`re_cENrXnX5_*`) | Old key was committed in `backend/auth_service/.env.example` and visible in git history | Stefan | <!-- docs-check: ignore -->
| 2026-05-01 | Migrated Supabase env from legacy JWT (`eyJ*`) to new key system (`sb_publishable_*` + `sb_secret_*`) | New format is independent of JWT secret rolls; legacy `eyJ*` JWTs returned by Management API after a roll were stale and broke prod | Stefan |

## Standing rules

- `.env*` files (except `.env.example`) are gitignored. `.env.example` files hold placeholders
  only; a real value in one is a leak: rotate the credential, then replace the file.
- Past commits are not rewritten. Rotation at the provider is the only valid remediation.
- Plans, post-mortems and docs redact secrets to a ≤12-char prefix + `*`, even after rotation
  (e.g. `re_cENrXnX5_*REDACTED*`).
- Suspected leak: rotate immediately if in doubt. External reports follow
  [`.github/SECURITY.md`](../.github/SECURITY.md).

## Rotating a secret

1. Rotate it at the provider (Supabase / Resend / Vercel / GitHub / DeepL).
2. Update it in the Vercel dashboard for every tier that uses it (backend variables live on
   `cms-backend-roman`) and in your local `backend/.env` / `frontend/.env.local`.
3. Redeploy, then check `/health`, `/content/<slug>`, `/auth/login` and `/forms/...`.
4. Add a row to the rotation log (redacted prefix only).

**Per-developer `.mcp.json` Supabase token** (`sbp_*`, gitignored, repo root). Rotate every
90 days: generate a new token in Supabase → Account → Access tokens (name
`claude-code-<YYYYMMDD>`), replace the `--access-token` value in `.mcp.json`, reload the Claude
Code session, revoke the old token, log it above.

## Settings that live outside the code (check quarterly)

| Where | Required |
|---|---|
| Vercel → `cms-backend-roman`, `roman-technologies` → Deployment Protection | Production OFF; preview SSO optional |
| Vercel → every client project → Deployment Protection | Production AND preview OFF (the dashboard's preview link must open without a login). The connector sets this; retrofit with `scripts/disable_vercel_auth.py` |
| Supabase → Storage → `cms-files` → Configuration | `file_size_limit` 52428800 (mirrors `MAX_FILE_SIZE` in `routers/workspace.py`); `allowed_mime_types` = the `_MIME_TO_EXT` list, **never** `image/svg+xml` (stored-XSS sink); `public` true |

## Threat model

Defended:
- **Tenant isolation:** one client's content, form submissions or config never reach another
  client. Enforced in FastAPI (ADR-0002); RLS is defense in depth only.
- **Admin authority:** `/admin/*` and `cmsk_*` Bearer keys run only for the operator
  (`users.is_admin` + key match; scoped keys only reach their `scopes`).
- **Credential confidentiality:** service-role key, Resend key, Vercel and Supabase PATs are never
  logged, returned, bundled into the client, or committed.
- **Session integrity:** `httponly`, `samesite=strict` in production, rotated on password change,
  revocable per device.

Out of scope: compromise of the operator's laptop or GitHub account, transitive supply-chain
attacks (mitigated by hash-pinned locks, SHA-pinned Actions and gitleaks, not eliminated), Vercel
platform compromise, physical/coercive attacks.

## Incident response

1. **Contain (≤15 min)**
   - Rotate the suspected credential ([Rotating a secret](#rotating-a-secret)).
   - Bearer admin keys (`cmsk_*`): mint a replacement with `scripts/mint_admin_api_key.py`, then
     revoke the old one in the SQL editor
     (`update admin_api_keys set revoked_at = now() where key_prefix = '<lookup>'`; the lookup is
     the third `_`-separated part of the key). Minting alone does not invalidate the old key.
   - Session compromise: call `revoke_all_for_user(user.id)` in the SQL editor.
2. **Assess (≤1 h):** pull Supabase auth logs and Vercel runtime logs for the window; match
   against `users.last_seen_at` and `sessions.created_at`; record IPs, user agents and affected
   `project_id`s privately.
3. **Notify (≤24 h):** if client data was affected, email that client with the scope, what was
   exposed and what was rotated. Operator-only credential: log the rotation, no notification.
4. **Remediate:** fix on a private branch → `dev` → verify → Promote dev → main. Never use
   `--no-verify`; the gitleaks hook stops a hot-fix from re-leaking.
5. **Post-mortem (≤7 days):** write it up (secrets redacted per the standing rules), add a
   rotation-log row if a credential was rotated, and add a finding to `FINDINGS.md` if the
   incident exposed an untracked class of bug.
