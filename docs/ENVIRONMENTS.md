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
| `SLACK_BOT_TOKEN` | optional | Bot User OAuth Token (`xoxb-...`) from the **CMS Issues Bot** Slack app. Disabled silently if unset. |
| `SLACK_ISSUES_CHANNEL_ID` | optional | Slack channel ID (e.g. `C0123ABCDEF`) for `#issues-websites`. Disabled silently if unset. |
| `CMS_DASHBOARD_URL` | optional | Base URL for the CMS dashboard, used as the "Open in CMS" button target in Slack messages. Defaults to `https://roman-technologies.dev`. |
| `AGENT_CACHE_ROOT` | optional (agents) | Filesystem root used by future S2/S3 issue-resolution agents (`<root>/<slug>` per project). Not consumed by S1. |
| `SLACK_SIGNING_SECRET` | optional | HMAC secret from Slack app → Basic Information. Required for `/slack/events` to accept any event; if unset, all signed events 401. |
| `SLACK_APPROVER_USER_ID` | optional | Stefan's Slack member ID (`U...`). Pins who can approve via ✅ or submit revisions via thread reply. |
| `SLACK_BOT_USER_ID` | optional | CMS Issues Bot's user ID. Used by message handler to ignore bot's own replies (loop guard). |
| `GITHUB_TOKEN` | optional | PAT with `repo` scope. Required for ✅ approval to fast-forward `master` to `cms-preview`. Reuses CMS Connector agent's token. |

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

## Scraper env contract — Hetzner box (`/etc/scraper.env`)

These vars live in `/etc/scraper.env` on the Hetzner cron box. They are **not**
on Vercel and the backend service does not import the scraper package — these two
deploy surfaces are fully independent.

| Var | Required in | Notes |
|-----|-------------|-------|
| `SUPABASE_URL` | required | `https://<ref>.supabase.co` — same value as backend. |
| `SUPABASE_SERVICE_KEY` | required | Service-role key that bypasses RLS. Same secret as backend's `SUPABASE_SERVICE_ROLE_KEY`. **Never expose.** |
| `GOOGLE_SHEETS_CREDENTIALS_JSON` | required | Filesystem path to the Google service-account JSON (e.g. `/etc/scraper/google-sa.json`). File must be owned `root:scraper`, mode `640`. |
| `GOOGLE_SHEET_ID` | required | Spreadsheet ID (the long key in the Google Sheets URL) for the leads mirror. |
| `SCRAPER_HEADLESS` | optional | Run Playwright headless. Default: `true`. Set `false` only for local debugging — headful mode won't work on the server. |
| `SCRAPER_LOCALE_DEFAULT` | optional | Browser locale passed to Playwright. Default: `en`. |
| `SCRAPER_USER_AGENT` | optional | Browser user-agent string. Default: Chromium 131 Windows UA (see `scraper/src/scraper/config.py`). |
| `SCRAPER_MIN_DELAY_MS` | optional | Minimum jitter delay between Maps requests (ms). Default: `600`. |
| `SCRAPER_MAX_DELAY_MS` | optional | Maximum jitter delay between Maps requests (ms). Default: `2200`. |

Log file lives at `/var/log/rt-scraper.log`, owned by `scraper:scraper`.
See `scraper/.env.example` for a ready-to-copy template and `scraper/deploy/DEPLOY.md`
for the full provisioning guide.
