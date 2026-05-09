# Development Lifecycle

How code travels from your editor to roman-technologies.dev. Read this once; from then on, the workflow is muscle memory.

If you are a new contributor, read [`docs/ONBOARDING.md`](./ONBOARDING.md) first — it walks the same flow with no jargon.

## TL;DR (the 30-second version)

1. `git checkout -b fix/<short-name>` (feature branch off `dev`)
2. Edit code.
3. `make ci` — local lint + tests (~20 s), optional but cheap.
4. `git commit -m "<type>: <what>"` — pre-commit hook runs lint + secret scan.
5. `git push origin fix/<short-name>` — feature-branch push runs **CI only** (~2-3 min). E2E and CodeQL stay quiet.
6. When the feature is done: `git checkout dev && git merge fix/<short-name> && git push origin dev`. Now the full pipeline fires.
7. `dev` push → CI + E2E + CodeQL all run. Auto-merge waits 60 s (debounce), verifies both green, fast-forwards `master`.
8. `master` push → Vercel auto-deploys backend + frontend. Post-deploy smoke probes the new URLs; auto-rollback fires on failure.

Total typical change → prod: **~6-10 minutes** from `git push origin dev`.

## Branches

| Branch | Purpose | Triggers on push | Protection |
|---|---|---|---|
| `fix/**`, `feat/**`, `chore/**`, `feature/**` | feature work — short-lived | CI only (lint + unit tests, no E2E) | none |
| `dev` | integration branch | CI + E2E + CodeQL | none (force-push allowed) |
| `master` | production tip | E2E (deployed_state slice) + CodeQL + post-deploy smoke | required status checks: `CI complete (gate)`, `E2E complete (gate)`. `enforce_admins=true`. |
| `dependabot/**` | auto-raised | CI only | auto-merged on green for patch + minor |

`dev` is "everything we believe should ship". `master` is "everything that has shipped". Never push to `master` directly except through the documented admin-bypass runbook.

## Why this layout

- **Feature branches**: cheap CI only — fast feedback while you iterate without burning E2E minutes.
- **`dev`**: integration point. Full pipeline. Must be green.
- **`master`**: production. Auto-promoted from `dev` once green; no human typing.
- **One automated path** — every change traverses identically. No "rush to prod" or "skip the tests" valves.

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
git push                 # → CI only (~2-3 min)
# repeat edits / commits / pushes; CI runs each time

# When done:
git checkout dev
git merge fix/something-short
git push origin dev      # → CI + E2E + CodeQL → auto-merge → master deploy
```

### Hot-fix

Same shape, just shorter cycle. The auto-merge debounce window (60 s) means if you push two fixes back-to-back, only the latest reaches `master`. That's intentional — saves a wasted Vercel build.

### Cross-cutting change (touches schema / auth / RLS)

- Land DB migrations as a **separate commit** before the code that depends on them. Apply via Supabase SQL editor, log in [`docs/SECURITY.md`](./SECURITY.md).
- Add a `pytest.mark.deployed_state` test if behaviour depends on the live deploy (security headers, rate-limit thresholds, RLS policies).
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

## CI / E2E pipeline

### CI (`.github/workflows/ci.yml`)

Triggered on:
- push to `master`, `dev`, `fix/**`, `feat/**`, `chore/**`, `feature/**`
- any pull request

Five jobs (path-filtered — only the changed-area jobs actually run):

| Job | What it runs |
|---|---|
| Detect changed paths | git diff vs parent; emits `backend / agent / frontend` booleans |
| Secret scan (gitleaks) | always |
| Backend (FastAPI) | ruff + black --check + pytest + **coverage gate (≥ 60 %)** |
| Agent (CMS Connector) | pytest |
| Frontend (Next.js) | tsc + ESLint + Prettier --check + vitest |
| `CI complete (gate)` | aggregator — single status check `master` requires |

### E2E (`.github/workflows/e2e.yml`)

Triggered on push to `dev` / `master` only — feature branches skip.

| Job | What it runs |
|---|---|
| Detect changed paths | skip on docs-only |
| Backend integration | pytest `tests_integration/`. **dev push**: `-m "integration and not deployed_state"`. **master push**: `-m "integration and deployed_state"` only (the rest already passed on `dev` for the same SHA). |
| Frontend E2E | Playwright. `PLAYWRIGHT_DEPLOYED_STATE=true` only on master push. |
| `E2E complete (gate)` | aggregator |

The deploy-readiness step (master only) polls backend `/health` AND frontend `/log-in` for up to 4 min each before kicking off the deployed_state suite, so we never race Vercel's edge.

### CodeQL (`.github/workflows/codeql.yml`)

Python + JavaScript/TypeScript matrix, `security-extended` query pack. Push to `master`/`dev` + Sundays 03:00 UTC.

### Auto-merge (`.github/workflows/auto-merge-dev-to-master.yml`)

`workflow_run` trigger after CI / E2E completes on `dev`. Sequence:

1. Sleep 60 s (debounce — collapses 5 rapid commits into 1 promotion).
2. Verify CI + E2E **both** completed `success` for the dev tip SHA.
3. Verify dev tip is still the SHA we were going to merge (otherwise a later commit handles itself).
4. Skip if the latest commit message contains `[skip-merge]`.
5. Fast-forward `master` to dev. Push.
6. Dispatch master-only workflows (E2E full suite, post-deploy smoke, CodeQL) since GitHub doesn't fire `push:` workflows on bot pushes.

### Post-deploy smoke (`.github/workflows/post-deploy-smoke.yml`)

Triggered after master push. Probes:
- `cms-backend-roman.vercel.app/health` → 200 + payload `"ok"`
- `cms-backend-roman.vercel.app/auth/me` (no cookie) → 401
- `roman-technologies.dev/log-in` → 200 + `Content-Security-Policy` header containing `frame-ancestors 'none'`

On any failure: `git revert HEAD` on master, push, open a P0 incident issue.

### Branch protection

`master` requires `CI complete (gate)` + `E2E complete (gate)`. Feature branches and PRs gate the same way; aggregator jobs accept `success` OR `skipped` (path-filtered no-runs count as pass), failure or cancellation is the only block.

## Vercel

| Project | URL | Auto-deploys from |
|---|---|---|
| `cms-backend-roman` | https://cms-backend-roman.vercel.app | `master` |
| `cms-frontend-roman` | https://roman-technologies.dev (custom domain) | `master` |
| Per-client | `<slug>.vercel.app` | per-project; managed by `agents/CMS Connector - Website` |

## Test markers (pytest)

| Marker | Where it runs | What it tests |
|---|---|---|
| (none) | every push, ms each | pure unit logic, mocks |
| `integration` | dev push (E2E job) | deployed backend, real network, no mocks |
| `deployed_state` | master push only, post-deploy | asserts the *freshly-deployed* code matches expectations (security headers, rate-limit thresholds, RLS policies) |

If you write a test that checks "the version of the code I just pushed is running" — mark it `deployed_state`. CI on dev will skip it; CI on master will run it after the deploy gate.

For Playwright tests with the same coupling, gate them with the `PLAYWRIGHT_DEPLOYED_STATE` env var (set to `"true"` only on master push by `e2e.yml`).

## Coverage

Backend tests must keep coverage ≥ 60 % (current ~ 66 %). The threshold is enforced by `pytest --cov-fail-under=60` in CI.

- Local check: `cd backend && pytest --cov` (config in `backend/.coveragerc`).
- Bump the floor in [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) when discipline rises sustainably.
- Excluded from measurement: `tests/`, `tests_integration/`, `migrations/`, `venv/`.

## Admin-bypass runbook (master push when CI/E2E gate fails)

Branch protection on `master` requires the two aggregator checks. Sometimes (e.g. a `deployed_state` catch-22) a dev push can't satisfy them until the master deploy lands. Procedure:

1. Confirm the failing checks are unrunnable, not actually red.
2. Disable enforce_admins:
   ```bash
   gh api -X DELETE repos/stefanroman22/cms-platform/branches/master/protection/enforce_admins
   ```
3. Push:
   ```bash
   git checkout master && git merge --ff-only origin/dev && git push origin master
   ```
4. Re-enable enforce_admins immediately:
   ```bash
   gh api -X POST repos/stefanroman22/cms-platform/branches/master/protection/enforce_admins
   ```
5. Note the bypass in the PR / commit body so the rotation log has audit trail.

This is a controlled escape hatch. Never use it because "tests are flaky and I'm in a hurry".

## When something breaks in prod

1. The auto-rollback workflow may have already reverted master. Check the issues tab — incident issue with label `incident,P0`.
2. Pull Vercel runtime logs (frontend + backend) for the deploy window.
3. If auto-rollback didn't fire and prod is still broken: `vercel rollback` via dashboard.
4. Fix on a feature branch, merge to dev, let the pipeline promote.
5. Document in [`docs/SECURITY.md`](./SECURITY.md) if user data was affected.

The post-mortem template lives at `docs/superpowers/post-mortems/YYYY-MM-DD-<slug>.md`.

## Tooling defaults

- **Python**: 3.13 (`.python-version`). Pinned via `setup-python` in CI.
- **Node**: read from `.nvmrc`. Pinned via `setup-node`.
- **Lockfiles**: `requirements.lock` + `requirements-dev.lock` (pip-compile, `--require-hashes`); `package-lock.json` (npm ci).
- **Pre-commit hooks** SHA-pinned in `.pre-commit-config.yaml`.
- **GitHub Actions**: every action SHA-pinned. Dependabot bumps weekly Mondays.

## Glossary

- **Feature branch**: any short-lived branch off `dev` named with `fix/`, `feat/`, `chore/`, `feature/` prefix.
- **Aggregator gate**: a single CI job that depends on every other job and `success|skipped` counts as pass. Branch protection points at the aggregator, not the individual jobs, so path-filtered skips don't block merges.
- **Debounce**: 60 s sleep at the start of auto-merge that lets rapid-fire commits collapse into a single master promotion.
- **`deployed_state`**: pytest marker (and Playwright env equivalent) for tests that need the just-deployed code running on the prod URL. Skipped pre-deploy, runs after.
