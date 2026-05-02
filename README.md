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

### Backend

```bash
cd backend
python -m venv venv
source venv/Scripts/activate     # Git Bash on Windows
pip install -r requirements.txt
cp .env.example .env             # then fill in SUPABASE_*, RESEND_*
uvicorn auth_service.main:app --reload --port 8001
```

`http://localhost:8001/health` → `{"status":"ok"}`.

### Frontend

```bash
cd frontend
npm install
cp .env.example .env.local       # FASTAPI_URL=http://localhost:8001 by default
npm run dev
```

`http://localhost:3000`.

### Tests

```bash
# Backend
cd backend && python -m pytest auth_service/tests/ -q

# Frontend
cd frontend && npm test

# Agent
cd "agents/CMS Connector - Website" && python -m pytest tests/ -q
```

## Production

Both services deploy to Vercel on push to `master`. Env vars live in each
Vercel project's dashboard, not in this repo. See
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
