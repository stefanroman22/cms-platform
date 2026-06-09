# Roman Technologies CMS

Headless CMS platform for managing client websites. Two services, one repo.

## Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│  cms-frontend-roman │  proxy  │  cms-backend-roman   │
│  (Next.js 15)       │ ──────▶ │  (FastAPI)           │
│  roman-technologies │         │  Vercel Python       │
│  .dev               │         │  serverless          │
└─────────────────────┘         └──────────┬───────────┘
                                           │
                                    ┌──────┴───────┐
                                    │   Supabase   │
                                    │   (Postgres) │
                                    └──────────────┘
```

- **`backend/`** — FastAPI service. Deployed by `backend/vercel.json` to
  `cms-backend-roman.vercel.app`. Handles auth (sid cookie), content
  read/write, forms (Resend), and admin endpoints.
- **`frontend/`** — Next.js dashboard at `roman-technologies.dev`. Talks
  to the backend via a server-side proxy at `/api/[...path]` so the
  browser never sees the FastAPI URL directly.
- **`agents/CMS Connector - Website/`** — Python CLI that scans a client
  website, generates the CMS provisioning manifest, creates services,
  deploys to Vercel, and onboards the client. See
  [`agents/README.md`](./agents/README.md).
- **`cms-client-template/`** — drop-in npm package that lets a client
  website call `/content/<slug>` and render CMS-driven content.

## Local development

Single entry point: the root `Makefile`. `make help` lists every target.

```bash
# First clone:
make install     # creates backend venv, installs all deps, sets up pre-commit hooks
make env         # bootstraps backend/.env and frontend/.env.local from .env.example

# Edit backend/.env (Supabase + Resend creds — see docs/ENVIRONMENTS.md)
# Edit frontend/.env.local (defaults to FASTAPI_URL=http://localhost:8001)

# Daily:
make dev         # prints the two terminal commands to run
make test        # all suites: backend pytest + agent pytest + frontend vitest
make lint        # ruff + black --check + ESLint + Prettier --check + tsc --noEmit
make format      # auto-fix everything (ruff --fix + black + prettier)
make ci          # same gate as GitHub Actions (lint + test)
```

### Run the servers directly (without `make`)

Two terminals — one for each service.

**Backend** → http://127.0.0.1:8001

```bash
cd backend
source venv/Scripts/activate
uvicorn auth_service.main:app --reload --port 8001
```

**Frontend** → http://localhost:3000

```bash
cd frontend
npm run dev
```

The `source venv/Scripts/activate` line is the Git Bash form on Windows. On macOS/Linux use `source venv/bin/activate`.

**Prerequisites**: Node ≥ 22 (pinned in `.nvmrc`), Python ≥ 3.13 (pinned in
`.python-version`). `nvm`/`pyenv` users auto-switch.

**Windows note**: `make` is not bundled with Git Bash. Install via
[Chocolatey](https://chocolatey.org/) (`choco install make`),
[Scoop](https://scoop.sh/) (`scoop install make`), or run inside WSL.

## Branching + release flow

Two branches:

- **`dev`** — your sandbox / integration workspace. Push here directly.
  Pushing to `dev` runs NO CI, checks, or workflows at all. Vercel
  auto-deploys a dev preview for both frontend
  (`roman-technologies-git-dev-*.vercel.app`) and backend
  (`cms-backend-roman-git-dev-*.vercel.app`).
- **`main`** — production. Protected: only the promote action writes to it
  (via a `PROMOTE_TOKEN` PAT). Humans never push to `main` directly.

Promotion to production is manual only, via the **Promote dev → main**
GitHub Action (GitHub → **Actions** → **Run workflow**, `workflow_dispatch`):

1. Gates, in order: frontend `npm ci && npm run lint && npm run build`;
   backend deps install (`pip install --require-hashes -r requirements.lock`)
   + `ruff check` + `python -m compileall`; and a `gitleaks` secret/token scan.
2. If ALL gates pass → fast-forwards `main` to `dev` and fires the Vercel
   production deploy hooks for both frontend (roman-technologies.dev) and
   backend (cms-backend-roman.vercel.app).
3. Any gate failure aborts and leaves `main` untouched.

There are no merge commits — only fast-forwards.

## Production

Both services deploy to Vercel production when the **Promote dev → main**
action fast-forwards `main`. Env vars live in each Vercel project's
dashboard, not in this repo. Note: dev and prod currently share the same
Supabase database (no dev DB isolation yet). See
[`docs/ENVIRONMENTS.md`](./docs/ENVIRONMENTS.md) for the full contract per
tier (development / preview / production).

## Security

Credential rotations are logged in [`docs/SECURITY.md`](./docs/SECURITY.md).
Suspected leak? Email stefanromanpers@gmail.com — don't open a public issue.

## Repository layout

```
.
├── backend/                       # FastAPI app served by Vercel Python
│   ├── auth_service/              # the actual app (routers, services, models)
│   ├── migrations/                # Supabase SQL migrations (NOT Django)
│   ├── vercel.json + vercel_entry.py
│   ├── requirements.txt
│   └── .env.example               # backend env template (no secrets)
├── frontend/                      # Next.js dashboard
│   ├── src/app/                   # App Router routes
│   │   └── api/[...path]/         # server-side proxy to FastAPI
│   ├── src/middleware.ts          # canonical-host redirect
│   └── .env.example               # frontend env template
├── agents/
│   ├── README.md                  # catalog of all agents
│   └── CMS Connector - Website/   # one of those agents
├── cms-client-template/           # drop-in for client websites
└── docs/
    ├── ENVIRONMENTS.md            # per-tier env-var contract
    ├── SECURITY.md                # credential rotation log + reporting
    └── superpowers/plans/         # implementation plans (this repo's history)
```
