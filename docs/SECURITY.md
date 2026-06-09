# Security Log

All credential rotations are recorded here. Do not delete entries — they
are the audit trail when a leak is suspected.

## Rotation log

| Date | What was rotated | Why | Operator |
|------|------------------|-----|----------|
| 2026-04-30 | Supabase legacy JWT secret (rolls both `anon` and `service_role`) | Old keys were committed in `backend/auth_service/.env.example` and visible in git history | Stefan |
| 2026-04-30 | Supabase database password | Old password was embedded in `SUPABASE_DB_URL` in committed `.env.example` files | Stefan |
| 2026-04-30 | Resend API key (`re_cENrXnX5_*`) | Old key was committed in `backend/auth_service/.env.example` and visible in git history | Stefan |
| 2026-05-01 | Migrated Supabase env from legacy JWT (`eyJ*`) to new key system (`sb_publishable_*` + `sb_secret_*`) | New format is independent of JWT secret rolls; legacy `eyJ*` JWTs returned by Management API after a roll were stale and broke prod | Stefan |

## Reporting a suspected leak

1. Email stefanromanpers@gmail.com.
2. Don't open a public issue. Don't push the details to a branch.
3. Rotate immediately if in doubt — rotations are cheap, breaches are not.

## Standing rules

- `.env*` files (except `.env.example`) are gitignored. The
  [`.gitignore`](../.gitignore) has explicit negation rules.
- `.env.example` files contain only **placeholder strings**. If you see a
  real value in one, treat it as a leak: rotate the credential and replace
  the file in a follow-up commit.
- Past commits cannot be sanitized without rewriting git history (which is
  out of scope). Rotation at the provider is the only valid remediation.
- **Plans, RFCs, post-mortems must redact secret values to ≤12-char
  prefix + `*` even after rotation.** Rotated keys still serve as
  patterns scanners flag and reveal credential-style information about
  the operator. Example: `re_cENrXnX5_*REDACTED*` not `re_cENrXnX5_25Ek...`.
- See [`docs/ENVIRONMENTS.md`](./ENVIRONMENTS.md) for the per-tier env-var
  contract.

## Vercel deployment-protection invariants

The Vercel projects are split into two categories with **opposite**
deployment-protection requirements. Audit quarterly that both still
hold.

### Backend / CMS infra projects (`cms-backend-roman`, `cms-frontend-roman`)

These run our own infrastructure and must be reachable from the public
internet (CMS clients call `cms-backend-roman` from their own websites,
and the operator and clients use `cms-frontend-roman` directly):

- **Vercel Authentication / SSO Protection: OFF** for production.
- **Preview deployments**: optional SSO is fine since previews are not
  client-facing.
- **DDoS / Trusted IPs**: not currently enforced. Future work
  (CI-allowlist for `/admin/*`) tracked as open audit item.

### Client website projects (e.g. `it-global-services`)

These are client-facing sites provisioned by the CMS Connector agent.
The client's visitors must reach the preview URL without an SSO gate,
because that's the URL the CMS dashboard's "See Preview" link opens.

- **Vercel Authentication / SSO Protection: OFF** for both production
  AND preview.
- This is set by `agents/CMS Connector - Website` during Phase 4
  provisioning (per the
  [`zero-prompt-agent design`](./superpowers/specs/2026-05-06-zero-prompt-agent-design.md)).
- The retrofit script for existing client projects lives at
  `scripts/admin/disable_vercel_auth.py` (planned — see audit item
  INFRA-009 for fail-closed guard).

### Quarterly verification

Open the Vercel dashboard, navigate to each project's
**Settings → Deployment Protection**, and confirm:

| Project | Production | Preview |
|---|---|---|
| `cms-backend-roman` | OFF | optional SSO OK |
| `cms-frontend-roman` | OFF | optional SSO OK |
| any `client-*` project | OFF | OFF |

If the agent stops correctly disabling SSO for new client projects, fix
it before onboarding the next client — a gated preview link is a
broken-onboarding bug for the client.

## Supabase Storage hardening

The `cms-files` bucket should have these defenses both in the
application layer (`backend/auth_service/routers/workspace.py`) AND
the bucket configuration. The application layer is the primary gate;
bucket-level limits are defense-in-depth for a future code path that
goes around the upload route (signed URL upload, direct REST call).

**Required bucket settings (Supabase dashboard → Storage → cms-files
→ Configuration):**

| Setting | Value | Why |
|---|---|---|
| `file_size_limit` | `52428800` (50 MB) | Mirror `MAX_FILE_SIZE` in [`backend/auth_service/routers/workspace.py`](../backend/auth_service/routers/workspace.py). |
| `allowed_mime_types` | `image/jpeg,image/png,image/gif,image/webp,video/mp4,video/webm,application/pdf` | Mirror `_MIME_TO_EXT`. **Do not include `image/svg+xml`** — XML payload can carry inline `<script>` and turns any public-URL render into a stored-XSS sink. |
| `public` | `true` | Required for public-URL serving on client websites. |

If a client genuinely needs SVG, the bucket must additionally serve
the file with `Content-Disposition: attachment` AND apply a CSP that
blocks scripts on the bucket origin. Until that work lands, SVG is
denied at the application layer (`_DENIED_MIME` set).

## Disclosure policy

This is a single-operator project. There is no bug-bounty programme and no
SLA. The expectations are:

- **Eligible findings**: any flaw that could compromise CMS clients
  (account takeover, cross-tenant data leak, RCE, credential exposure,
  privilege escalation, persistent XSS, RLS bypass).
- **Out of scope**: best-practice nits without a concrete impact path,
  rate-limit fuzzing without a working bypass, social engineering of the
  operator, anything requiring physical access.
- **Coordinated disclosure window**: 90 days from acknowledgement, or
  immediately upon public deployment of a fix — whichever is sooner.
- **Acknowledgement**: best-effort within 7 days. Reporters who follow
  the process get a public credit in the rotation log if they want one.

## Threat model (scope)

What the platform is defending:

- **Tenant isolation** — one client's CMS content / form submissions /
  service config must never leak into another client's frontend or
  another client's API responses. Boundary: `projects.user_id` +
  `project_services.project_id` chain, enforced by application-layer
  filters today and Postgres RLS (BE-010, defense-in-depth —
  service-role bypasses RLS today, but anon-bound regressions return
  zero rows instead of cross-tenant data).
- **Admin endpoint authority** — `/admin/*` and the `cmsk_*` Bearer key
  path must only run for the operator. Boundary: `users.is_admin = true`
  *and* admin-API-key match. Scope-restricted Bearer keys (e.g. agent
  scope) can only call the endpoints listed in their `scopes` array.
- **Credential confidentiality** — Supabase service-role key, Resend API
  key, Vercel PAT, Supabase PAT must never be logged, returned in API
  responses, embedded in client bundles, or written to commit history.
- **Session integrity** — session cookies are httponly, samesite=strict
  in production, rotated on password change, revocable per-device, and
  bound to user-agent + IP for audit.

What is **explicitly out of scope** for the threat model:

- Compromise of the operator's laptop or GitHub account (defended at the
  GitHub layer: 2FA, branch protection, push protection — see CI-009).
- Supply-chain attacks on transitive npm/pypi packages (mitigated by
  `--ignore-scripts` on `npm ci` + Dependabot + gitleaks, but not zero).
- Vercel platform compromise (vendor-trust boundary).
- Physical / coercive attack on the operator.

## Defense layers

What hardening is in place per layer:

- **RLS layer** — Every tenant-scoped table (`users`, `sessions`,
  `projects`, `content_entries`, `project_issues`, `project_requests`)
  has Row-Level Security enabled with owner policies
  (`user_id = auth.uid()`). The backend uses the service-role client
  which bypasses RLS by design — the policies are defense-in-depth
  against future code that uses an anon-bound client or a refactor
  that drops a `.eq("user_id", uid)` filter. Migration:
  `backend/migrations/2026_05_09_tenant_tables_rls.sql`. Presence
  test: `auth_service/tests_integration/test_rls_policies.py`.
- **Bearer auth path rate-limit** — `Authorization: Bearer cmsk_…`
  requests are gated at 10 attempts / minute / IP (in-memory token
  bucket per serverless instance). Every parse-fail path runs
  `argon2.verify` against a precomputed dummy hash so wall-clock time
  is independent of where validation failed (closes BE-011 / CWE-208).
  Module: `backend/auth_service/core/bearer_limiter.py`.
- **Login rate-limit** — `/auth/login` is gated at 30/minute/IP
  (BE-002, raised from 10 for typo tolerance). Same `client_ip()`
  resolver as the Bearer path; also runs argon2 verify against a
  dummy hash on the email-not-found branch to close the account-
  enumeration timing oracle.
- **Form-submit rate-limit** — `submit_form` is gated at
  5/10minutes/(slug:form:ip) bucket (BE-001), so an attacker
  hammering one project's form can't burn another project's quota.
- **Session integrity** — see Standing rules above for cookie flags.

## Incident response runbook

Trigger: suspected leak, observed unauthorized access, anomalous traffic,
externally-reported finding.

1. **Contain (≤15 min)**
   - Rotate the suspected credential at the provider (Supabase / Resend /
     Vercel / GitHub PAT). Use the procedure in
     [`docs/ENVIRONMENTS.md`](./ENVIRONMENTS.md).
   - For Bearer admin keys (`cmsk_*`): regenerate via `scripts/auth/`
     helpers — old key invalidates immediately.
   - For session compromise: call `revoke_all_for_user(user.id)` directly
     against the database via Supabase SQL editor.

2. **Assess (≤1 h)**
   - Pull Supabase auth logs + Vercel runtime logs for the suspected
     window. Match against `users.last_seen_at` + `sessions.created_at`.
   - For data-exposure suspicions: query `content_entries` /
     `project_services` / `users` for rows touched in the window.
   - Document IPs, user-agents, affected `project_id`s in the incident
     ticket (private).

3. **Notify (≤24 h)**
   - If a CMS client's data was affected: email the client directly with
     the scope, what was exposed, what was rotated.
   - If only operator credentials were affected and no client data was
     touched: log in the rotation table above; no client notification.

4. **Remediate**
   - Open a private fix branch. Land the patch on `dev` first, verify it
     locally, then promote to production via the **Promote dev → main**
     action (build + gitleaks gate).
   - Never disable hooks (`--no-verify`) during incident response —
     gitleaks pre-commit is what stops the hot-fix from re-leaking.

5. **Post-mortem (≤7 days)**
   - Write up the incident in `docs/superpowers/post-mortems/YYYY-MM-DD-<slug>.md`.
   - Redact secret values (≤12-char prefix + `*`) per the standing rule
     above, even though the credential is already rotated.
   - Add a row to the rotation log if a credential was rotated.
   - Add a finding to the next security audit if the incident exposed a
     class of vulnerability not previously tracked.
