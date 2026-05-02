# Deploy scripts

One-shot Python scripts that bootstrap Vercel projects for the two CMS
services. Each script is idempotent: re-running on an existing project
is a no-op.

## When to use

Only when you need to spin up a fresh Vercel project (e.g. forking the
CMS into a parallel staging environment). The current production
projects (`cms-backend-roman` and `cms-frontend-roman`) were created
using these scripts.

## Prerequisites

```bash
export VERCEL_TOKEN=<personal access token from https://vercel.com/account/tokens>
export SUPABASE_URL=...
export SUPABASE_ANON_KEY=...
export SUPABASE_SERVICE_ROLE_KEY=...
export RESEND_API_KEY=...
```

## Run

```bash
python scripts/deploy/create_backend_vercel_project.py
python scripts/deploy/create_frontend_vercel_project.py
```

## What they do

- Create the Vercel project linked to the GitHub repo.
- Set every env var listed in `docs/ENVIRONMENTS.md` for all three Vercel
  environments (Production, Preview, Development).
- Configure the project's `rootDirectory` (`backend/` or `frontend/`).

## After running

Push to `master` triggers the actual first deploy. Confirm the live
endpoints respond:

```bash
curl -s https://cms-backend-roman.vercel.app/health
# → {"status":"ok"}
```

Update [`docs/ENVIRONMENTS.md`](../../docs/ENVIRONMENTS.md) if the new
project introduces new env vars or different defaults.
