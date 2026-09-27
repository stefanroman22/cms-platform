# CLAUDE.md

Headless CMS for small-business client sites: FastAPI `backend/` (Vercel `cms-backend-roman`), Next.js 16 `frontend/` (Vercel `roman-technologies`), Supabase.

## Run

- `make install && make env` — first-time setup (venv at `backend/venv`, npm ci, pre-commit hook, `.env` files)
- Windows: Git Bash has no `make`; install it with `choco install make` or `scoop install make`
- `make ci` — full lint + tests, the only test gate. Run it at plan checkpoints and before handing work back, not after each edit
- `make test-backend` / `make test-agent` / `make test-frontend` — one suite
- `cd e2e && npm test` — Playwright E2E against deployed URLs, run by hand. First time: `npm install && npx playwright install chromium`, copy `.env.example` → `.env.local` (E2E passwords from the password manager); set `PLAYWRIGHT_DEPLOYED_STATE` for deployed-build tests
- `make format` — ruff --fix + black + prettier
- `cd backend && source venv/Scripts/activate && uvicorn auth_service.main:app --reload --port 8001`
- `cd frontend && npm run dev` (:3000). Don't `npm run build` while it runs; that kills the dev server
- `python scripts/apply_supabase_migration.py backend/migrations/<file>.sql` (or Supabase MCP `apply_migration`); this applies it to prod

## Safety (non-negotiable)

- **IMPORTANT: one Supabase DB (`xeluydwpgiddbamysgyu`) serves local, preview and prod. Every write, script, migration and local server run hits production data.**
- Migrations are SQL in `backend/migrations/YYYY_MM_DD_<name>.sql`, applied by hand. Apply before or with the code that needs them (a missing column 500s every endpoint that selects it).
- Never edit a migration that has already been applied; add a new file.
- `backend/.env` holds prod keys and `main.py` loads it: backend tests that reach Supabase must use the `mock_supabase` fixture; never let a test call Resend/DeepL for real.
- `backend/auth_service/tests_integration/` and `e2e/` hit deployed URLs or the real DB. Run them only on purpose, against the dev preview, before promoting.
- Production is `main` and changes only through the manual "Promote dev → main" action. Never push to `main`.
- Prod broken: roll back in the Vercel dashboard (there is no automatic rollback), then fix on a branch → `dev` → promote.
- Pushes run no CI. Pushing to `dev` auto-deploys Vercel previews (on the prod DB). The promote gate is gitleaks + lint + build, with no tests.
- Never use `git commit --no-verify`. The pre-commit hook is the only secret scan before push.
- Never put a password or other secret in an email body.
- Env vars the FastAPI code reads go on Vercel `cms-backend-roman`; the frontend project needs only `FASTAPI_URL`. The wrong project fails silently.
- `security/` is written by scheduled review/fix routines. Keep its paths and format.

## Before you touch

- Architectural decisions live in `docs/decisions/`. Read the relevant ADR before changing the database or migrations, data access or the API proxy, auth, backend runtime or scheduling, draft/publish, the public client-site API, the release pipeline, multi-language content, or environments, config and CORS.
- An agent in `agents/<name>/` (running or changing it): its `AGENTS.md` is the only definition; read it and `LEARNINGS.md` first. Append to `LEARNINGS.md`; never rewrite it.
- Transactional email: read `backend/auth_service/services/email_layout.py`. Build every email from `shell` + `header` + `accent_rule` + body helpers + `footer`, with no standalone HTML templates.
- Email content: `html.escape` untrusted text; pass URLs and colours through `safe_url` / `safe_hex`.
- Rotating a secret (including the `.mcp.json` Supabase token, every 90 days): follow and log it in `security/RUNBOOK.md`.
- A client-site repo: `cms-preview` is its preview branch (reads drafts) and goes stale; refresh it with `git push origin <prod>:cms-preview`. Its prod branch (`projects.production_branch`) must stay unprotected on GitHub. Content changes need no deploy.

## Conventions

- Import animation from `motion/react`, never `framer-motion` (enforce via lint).
- Python deps: edit `requirements*.txt`, then regenerate the hashed `.lock` with `pip-compile --generate-hashes`. Vercel installs the `.txt`; the promote gate installs the `.lock`.
- New env var: add it to `.env.example`, to `Settings` in `backend/auth_service/core/config.py`, and to Vercel for each tier; add a `model_validator` if it's required.
- If a change invalidates a doc, fix or delete the doc in the same commit.
- Specs/plans that planning skills write under docs/superpowers are temporary: delete them once the work is committed and stable.
