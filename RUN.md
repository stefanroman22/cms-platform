# Run it locally

My cheat sheet. Commands are for PowerShell, run from the repo root unless a `cd` says otherwise.

> Local servers use the **production** database. Anything you create or delete locally is real.

## First time only

```powershell
make install     # backend venv + all deps + pre-commit hook   (no make? choco install make)
make env         # creates backend\.env and frontend\.env.local, asks for the values
```

## Start everything (two terminals)

**Terminal 1 — backend** → http://127.0.0.1:8001 (API docs: http://127.0.0.1:8001/docs)

```powershell
cd backend
.\venv\Scripts\python -m uvicorn auth_service.main:app --reload --port 8001
```

**Terminal 2 — frontend** → http://localhost:3000 (dashboard: http://localhost:3000/dashboard)

```powershell
cd frontend
npm run dev
```

Stop either with `Ctrl+C`. Don't run `npm run build` while the frontend is running; it kills the dev server.

## Check before pushing

```powershell
make ci          # lint + every test suite (~1-3 min)
make format      # auto-fix formatting if lint complains
```

One suite only: `make test-backend`, `make test-frontend`, `make test-agent`.

## End-to-end tests (hit the deployed site, not localhost)

```powershell
cd e2e
npm install; npx playwright install chromium      # first time
copy .env.example .env.local                       # first time: fill in the E2E passwords
npm test                                           # or: npm run test:headed / test:ui / report
```

## Database migration (changes production immediately)

```powershell
python scripts\apply_supabase_migration.py backend\migrations\<file>.sql
```

Needs `SUPABASE_PAT` and `SUPABASE_PROJECT_REF` set. Or paste the SQL into the Supabase SQL editor.

## Ship to production

Push to `dev` (Vercel builds a preview), check it, then GitHub → Actions → **Promote dev → main** → Run workflow.
