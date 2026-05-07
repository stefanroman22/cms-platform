# Environments

Three tiers: **development**, **preview**, **production**. Each maps to a
specific deploy surface and a specific source of env vars.

## Tier matrix

| Tier | Where it runs | Source of env vars | Trigger |
|------|---------------|-------------------|---------|
| development | your laptop | `backend/.env` + `frontend/.env.local` (gitignored) | `uvicorn` / `npm run dev` |
| preview | Vercel preview deployment | Vercel dashboard → Preview env | push to any non-`master` branch |
| production | Vercel production deployment | Vercel dashboard → Production env | merge to `master` |

The backend reads `ENVIRONMENT` (`Literal["development","preview","production"]`)
to branch CORS + Private Network Access logic. Anything else is rejected at
startup.

## Backend env contract — `cms-backend-roman`

| Var | Required in | Notes |
|-----|-------------|-------|
| `ENVIRONMENT` | all | Drives CORS + PNA. Typed Literal — typos crash startup. |
| `SUPABASE_URL` | all | `https://<ref>.supabase.co` |
| `SUPABASE_ANON_KEY` | all | Use `sb_publishable_*` (newer system). Public-readable; safe in client bundles if needed. |
| `SUPABASE_SERVICE_ROLE_KEY` | all | Use `sb_secret_*`. **Server-only — bypasses RLS.** Never expose. |
| `SUPABASE_DB_URL` | optional | Only used for ad-hoc psql, not by the app. |
| `FRONTEND_ORIGINS` | **production only** | Comma-separated list. App refuses to start in prod without this. |
| `RESEND_API_KEY` | preview + production | Sends transactional + welcome email. |
| `RESEND_FROM_EMAIL` | optional | Defaults to `noreply@roman-technologies.dev` (verified in Resend). |
| `RESEND_FROM_NAME` | optional | Defaults to `Roman Technologies CMS`. |

## Frontend env contract — `cms-frontend-roman`

| Var | Required in | Notes |
|-----|-------------|-------|
| `FASTAPI_URL` | all | Server-only. Used by `app/api/[...path]/route.ts` to proxy. Set per tier. |

## What lives where

- **Local secrets**: `backend/.env` (auto-loaded by pydantic-settings via
  `parents[2] / .env`) and `frontend/.env.local` (auto-loaded by Next.js).
  Both gitignored.
- **Production secrets**: Vercel dashboard → project → Settings → Environment Variables.
- **Examples**: `backend/.env.example` + `frontend/.env.example`. Both committed,
  both contain only placeholder values.
- **Per-developer MCP secrets**: `.mcp.json` at the repo root. Contains a
  Supabase Personal Access Token (`sbp_*`) for the Supabase MCP server.
  Gitignored — never commit. Rotate every 90 days; log in `docs/SECURITY.md`.
  Procedure:
  1. Supabase dashboard → Account → Access tokens → Generate new token (name `claude-code-<YYYYMMDD>`).
  2. Replace the value in `.mcp.json:9` (`--access-token`).
  3. Restart any tool that reads `.mcp.json` (Claude Code session reload).
  4. Revoke the previous token in the dashboard.
  5. Log the rotation in `docs/SECURITY.md` rotation log.

## Adding a new env var

1. Add it to the relevant `.env.example` (placeholder value).
2. Add it to the typed `Settings` class in `backend/auth_service/core/config.py`
   (backend) or document it in `frontend/.env.example` (frontend).
3. Set it in the Vercel dashboard for every tier that needs it.
4. If it's required at runtime, add a `model_validator` so the app fails to
   start when missing in that tier. Silent fallbacks cause the hardest
   production bugs.

## Rotating a secret

See [`docs/SECURITY.md`](./SECURITY.md) for the rotation log + procedure.
After rotating in the provider, update Vercel dashboard, redeploy, and verify
the live endpoints (`/health`, `/content/<slug>`, `/auth/login`, `/forms/...`).
