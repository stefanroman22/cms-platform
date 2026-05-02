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
- See [`docs/ENVIRONMENTS.md`](./ENVIRONMENTS.md) for the per-tier env-var
  contract.
