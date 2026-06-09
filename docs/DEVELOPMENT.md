# Development Lifecycle

How code travels from your editor to roman-technologies.dev. Read this once; from then on, the workflow is muscle memory.

If you are a new contributor, read [`docs/ONBOARDING.md`](./ONBOARDING.md) first — it walks the same flow with no jargon.

## TL;DR (the 30-second version)

1. `git checkout -b fix/<short-name>` (feature branch off `dev`)
2. Edit code.
3. `make ci` — local lint + tests (~20 s), optional but cheap.
4. `git commit -m "<type>: <what>"` — pre-commit hook runs lint + secret scan.
5. `git push origin fix/<short-name>` — feature-branch push runs **nothing** in GitHub Actions. Verify locally.
6. When the feature is done: `git checkout dev && git merge fix/<short-name> && git push origin dev`. No CI runs; Vercel auto-deploys a dev preview for both frontend + backend.
7. Smoke-test the dev preview (`roman-technologies-git-dev-*.vercel.app` / `cms-backend-roman-git-dev-*.vercel.app`).
8. When dev looks good: run the **"Promote dev → main"** GitHub Action manually (Actions tab → Run workflow). It gates on frontend lint+build, backend deps+ruff+compile, and a gitleaks scan; if all pass it fast-forwards `main` to `dev` and fires the Vercel production deploy hooks for backend + frontend.

Total typical change → prod: a manual promote run (~2-4 minutes of gates) after you're happy with the dev preview.

## Branches

| Branch | Purpose | Triggers on push | Protection |
|---|---|---|---|
| `fix/**`, `feat/**`, `chore/**`, `feature/**` | feature work — short-lived | none (no CI / checks) | none |
| `dev` | integration workspace | none (no CI / checks); Vercel auto-deploys a dev preview for frontend + backend | none (force-push allowed) |
| `main` | production tip | nothing on push — production deploy hooks fire from the promote action | protected: only the "Promote dev → main" action writes to it (via `PROMOTE_TOKEN` PAT). |

`dev` is "everything we believe should ship". `main` is "everything that has shipped". Humans never push to `main` directly — they push to `dev` and run the promote action.

## Why this layout

- **Feature branches**: no CI — fast iteration; verify locally with `make ci`.
- **`dev`**: integration point. Vercel auto-deploys a dev preview so you can eyeball the change end-to-end before promoting.
- **`main`**: production. Promoted from `dev` only by a manual run of "Promote dev → main", which gates before it fast-forwards.
- **One promotion path** — production only ever advances through the promote action; no human typing into `main`.

## Daily flow

### Routine change

```bash
git checkout dev
git pull
git checkout -b fix/something-short
# edit
make ci          # local guard: ruff + black + tsc + vitest + pytest
git add -p
git commit -m "feat(workspace): add <thing>"
git push                 # → no CI; verify locally
# repeat edits / commits / pushes

# When done:
git checkout dev
git merge fix/something-short
git push origin dev      # → no CI; Vercel auto-deploys a dev preview
# eyeball the dev preview, then run the "Promote dev → main" Action to ship
```

### Hot-fix

Same shape, just shorter cycle. Push to `dev`, confirm the dev preview, then run the promote action. Because promotion is manual, only what you explicitly promote reaches `main`.

### Cross-cutting change (touches schema / auth / RLS)

- Land DB migrations as a **separate commit** before the code that depends on them. Apply via Supabase SQL editor, log in [`docs/SECURITY.md`](./SECURITY.md). Note: `dev` and production currently **share the same Supabase database** — there is no dev DB isolation yet, so a migration applied for `dev` also affects production.
- Smoke-test behaviour that depends on the live deploy (security headers, rate-limit thresholds, RLS policies) against the dev preview before promoting.
- Update [`docs/SECURITY.md`](./SECURITY.md) if the threat model shifts.

## Local commands (`make`)

| Target | What it does |
|---|---|
| `make install` | first-time setup (venv, npm ci, pre-commit install) |
| `make env` | interactive env-var bootstrap |
| `make dev` | prints backend + frontend dev-server commands |
| `make test` | every test suite |
| `make test-backend` / `test-agent` / `test-frontend` | per-area |
| `make lint` | ruff + black --check + tsc + ESLint + Prettier |
| `make format` | auto-fix everything |
| `make ci` | the same checks GitHub Actions runs |

## Pre-commit

Installed by `make install`. Runs on every `git commit`:

- `ruff` (Python lint + auto-fix)
- `ruff-format` (Python format)
- `black` (Python format — pinned to CI version)
- `gitleaks` (secret scanning, custom rules in [`.gitleaks.toml`](../.gitleaks.toml))
- `lint-staged` on staged JS/TS/CSS (Prettier + ESLint)
- standard hygiene: trailing-whitespace, end-of-file, check-yaml, check-toml, large-files, merge-conflict markers

**Tests do NOT run in pre-commit.** Too slow. CI catches them.

## Pipeline

As of 2026-06-09 the old auto-gated pipeline (CI / E2E / auto-merge / post-deploy smoke on every push) is gone. There is now exactly one CI surface: the manual promote action. Everything else runs in Vercel previews or locally.

### Pushes run nothing

Pushing to a feature branch or to `dev` runs **no** GitHub Actions checks. Vercel auto-deploys a **dev preview** for both projects on every `dev` push:
- Frontend: `roman-technologies-git-dev-*.vercel.app`
- Backend: `cms-backend-roman-git-dev-*.vercel.app`

Verify your change locally (`make ci`) and on the dev preview. There is no automated gate before `dev`.

### Promote dev → main (`.github/workflows/promote.yml`)

**Manual only.** Actions tab → "Promote dev → main" → Run workflow. This is the single CI surface. It runs these gates, in order:

1. **Frontend** — `npm ci && npm run lint && npm run build`.
2. **Backend** — deps install (`pip install --require-hashes -r requirements.lock`) + `ruff check` + `python -m compileall`.
3. **Secret scan** — `gitleaks`.

If **all** gates pass, it **fast-forwards `main` to `dev`** (writing with the `PROMOTE_TOKEN` PAT, since `main` is protected) and fires the Vercel **production** deploy hooks for both projects:
- Frontend → roman-technologies.dev
- Backend → cms-backend-roman.vercel.app

Any gate failure aborts the run and leaves `main` untouched — nothing deploys.

### CodeQL (`.github/workflows/codeql.yml`)

Python + JavaScript/TypeScript matrix, `security-extended` query pack. **Weekly-scheduled only — Sundays 03:00 UTC**, no push trigger. Findings land in the **Security → Code scanning** tab.

### Solver Agent (`.github/workflows/solver-agent.yml`)

Issue-resolution agent. Triggered by `repository_dispatch` (issue tick) plus an hourly schedule. Unaffected by the pipeline change — still running.

### Branch protection

`main` is protected so only the promote action can write to it (via `PROMOTE_TOKEN`). There are no required status-check gates anymore — the promote action *is* the gate, and it only fast-forwards `main` once its own checks pass.

## Vercel

| Project | URL | Production deploy |
|---|---|---|
| `cms-backend-roman` | https://cms-backend-roman.vercel.app | deploy hook fired by the promote action when `main` advances; auto-deploys a dev preview (`cms-backend-roman-git-dev-*.vercel.app`) on every `dev` push |
| `cms-frontend-roman` | https://roman-technologies.dev (custom domain) | deploy hook fired by the promote action when `main` advances; auto-deploys a dev preview (`roman-technologies-git-dev-*.vercel.app`) on every `dev` push |
| Per-client | `<slug>.vercel.app` | per-project; managed by `agents/CMS Connector - Website` |

## Test markers (pytest)

| Marker | Where it runs | What it tests |
|---|---|---|
| (none) | locally / `make ci`, ms each | pure unit logic, mocks |
| `integration` | locally on demand (no longer in any GitHub workflow) | deployed backend, real network, no mocks |
| `deployed_state` | locally against the dev preview or prod URL (no longer in any GitHub workflow) | asserts the *deployed* code matches expectations (security headers, rate-limit thresholds, RLS policies) |

If you write a test that checks "the version of the code I just pushed is running" — mark it `deployed_state` and run it manually against the dev preview before you promote. No GitHub workflow runs these markers anymore.

For Playwright tests with the same coupling, gate them with the `PLAYWRIGHT_DEPLOYED_STATE` env var and run them locally against the dev preview.

## Coverage

Backend tests should keep coverage ≥ 60 % (current ~ 66 %). With the old `ci.yml` gone, this is no longer enforced by a GitHub workflow — it's a local discipline you run before promoting.

- Local check: `cd backend && pytest --cov --cov-fail-under=60` (config in `backend/.coveragerc`).
- Excluded from measurement: `tests/`, `tests_integration/`, `migrations/`, `venv/`.

## Promoting to production

There is no admin-bypass anymore. `main` is protected so only the "Promote dev → main" action can write to it (via the `PROMOTE_TOKEN` PAT). To ship:

1. Get your change onto `dev` and confirm the dev preview looks right.
2. Actions tab → **"Promote dev → main"** → Run workflow.
3. The action runs its gates (frontend lint+build, backend deps+ruff+compile, gitleaks). If all pass it fast-forwards `main` to `dev` and fires the production deploy hooks.
4. If a gate fails, the run aborts and `main` is untouched — fix on `dev` and re-run.

Never try to push to `main` directly; branch protection rejects it. The promote action is the only path.

## When something breaks in prod

1. There is no auto-rollback anymore. If prod is broken, roll back the Vercel production deployment via the dashboard (`vercel rollback`) — that's the fastest stop-the-bleeding move.
2. Pull Vercel runtime logs (frontend + backend) for the deploy window.
3. Fix on a feature branch, merge to `dev`, confirm the dev preview, then run the promote action to ship the fix.
4. Document in [`docs/SECURITY.md`](./SECURITY.md) if user data was affected.

The post-mortem template lives at `docs/superpowers/post-mortems/YYYY-MM-DD-<slug>.md`.

## Tooling defaults

- **Python**: 3.13 (`.python-version`). Pinned via `setup-python` in the promote action.
- **Node**: read from `.nvmrc`. Pinned via `setup-node`.
- **Lockfiles**: `requirements.lock` + `requirements-dev.lock` (pip-compile, `--require-hashes`); `package-lock.json` (npm ci).
- **Pre-commit hooks** SHA-pinned in `.pre-commit-config.yaml`.
- **GitHub Actions**: every action SHA-pinned. Dependabot has been removed — dependency bumps are manual.

## Slack notifications in local dev

`backend/auth_service/services/slack_notify.py` is silent unless both `SLACK_BOT_TOKEN` and `SLACK_ISSUES_CHANNEL_ID` are set. Local dev does not need to configure Slack; tests use mocks. To smoke-test for real, copy the prod values into `backend/.env` and POST an issue.

## Glossary

- **Feature branch**: any short-lived branch off `dev` named with `fix/`, `feat/`, `chore/`, `feature/` prefix.
- **Dev preview**: the Vercel deployment Vercel auto-builds for both projects on every `dev` push (`*-git-dev-*.vercel.app`). Where you smoke-test before promoting.
- **Promote action**: the manual "Promote dev → main" GitHub Action — the only CI surface and the only writer to `main`.
- **`deployed_state`**: pytest marker (and Playwright env equivalent) for tests that need deployed code running on a live URL. No longer run by any workflow — run them locally against the dev preview before promoting.
