# ADR-0003: Own session auth, not Supabase Auth

Status: Accepted
Date: 2026-09-27

## Context

Dashboard users are the operator (admin) and a handful of small-business clients. Accounts are
created by the operator, not by public sign-up. Agents and scripts also need to call admin
endpoints without a browser. Supabase Auth would add JWT handling in the frontend, and it does not
fit well with ADR-0002 (no Supabase in the browser).

## Decision

- Dashboard login uses an opaque `sid` session cookie with a sliding lifetime. Only a hash of the
  session id is stored, in the `sessions` table (`services/sessions.py`); passwords are hashed with
  argon2 (`routers/auth.py`). Supabase Auth is not used.
- There is one role flag: `users.is_admin`. Admins see and manage every project; a client sees only
  projects where `projects.user_id` is theirs (`routers/deps.py`).
- Accounts are provisioned by the operator (`POST /admin/clients`). Passwords are reset only by the
  operator (`POST /admin/clients/{email}/reset-password`); there is no self-serve reset. Every
  password change emails a notice that never contains the password.
- Agents and scripts authenticate with `Authorization: Bearer cmsk_…` admin API keys
  (`services/admin_keys.py`, minted by `scripts/mint_admin_api_key.py`), rate-limited and
  timing-equalised (`core/bearer_limiter.py`).

## Consequences

- Sessions can be revoked instantly by deleting rows. The frontend handles no tokens. Cookie and
  key auth resolve to the same `UserOut` type in `deps.py`.
- The team owns the security of login, lockout, session expiry and key handling itself. This code
  is reviewed by the weekly `security/` routine.
- No roles beyond admin/client, and no self-serve recovery: a locked-out client needs the operator.
- Do NOT: introduce Supabase Auth, JWTs in the browser, a public sign-up flow or a password-reset
  email that carries a password or a long-lived link, or add roles by sprinkling new boolean
  checks. Each of these needs a new ADR.
