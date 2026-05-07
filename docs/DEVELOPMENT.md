# Development Lifecycle

How code travels from your editor to roman-technologies.dev. Read this once; from then on, the workflow is muscle memory.

## TL;DR (the 30-second version)

1. `git checkout dev && git pull`
2. Edit code.
3. `make ci` (lint + tests, ~20 s) — optional but recommended.
4. `git commit -m "<type>: <what>"` — pre-commit hook runs lint + secret scan.
5. `git push origin dev` — CI + E2E run automatically. ~3-4 min wall time.
6. Merge to `master` lands automatically (post-PR-5 — see [Roadmap](#roadmap)). Until then: `gh workflow run "Scheduled merge dev → master"` triggers it on demand.
7. Vercel auto-deploys backend + frontend from `master`. ~2-3 min.

Total typical change → prod: ~6-10 min.

## Branches

| Branch | Purpose | Protection |
|---|---|---|
| `dev` | day-to-day development | unprotected (force-push allowed) |
| `master` | production tip | required status checks: `ci-complete`, `e2e-complete`. `enforce_admins=true` (admin override needs the runbook below). |
| `dependabot/*` | auto-raised by Dependabot | unprotected; auto-merged on green CI for patch + minor (post-PR-7). |

`dev` is "everything goes". `master` is "everything is true". Never push to master directly except through the merge flow.

## Daily flow

### Routine change (no schema, no auth, no RLS)

```bash
git checkout dev
git pull
# edit
make ci          # local guard: ruff + black + tsc + vitest + pytest
git add -p
git commit -m "feat(workspace): add <thing>"
git push
```

CI + E2E run on the push. If both green, the next scheduled-merge run promotes `dev → master`.

### Cross-cutting change (touches >1 area, or schema, or auth, or RLS)

Same flow, plus:

- Add a `pytest.mark.deployed_state` integration test if behavior depends on the deployed environment (security headers, rate-limit thresholds, RLS).
- Update [`docs/SECURITY.md`](./SECURITY.md) if the threat model shifts.
- Land any DB migration as a separate commit *before* the code that depends on it; apply via Supabase dashboard, log in [`docs/SECURITY.md`](./SECURITY.md) rotation table.

### Hot-fix

- Fix on `dev`. Push.
- If you need it in prod immediately (don't wait for the next scheduled merge):
  ```bash
  gh workflow run "Scheduled merge dev → master"
  ```
- The workflow is gated by green CI + E2E on dev tip. If the gate refuses, fix the failing check first.

## Local commands (`make`)

| Target | What it does |
|---|---|
| `make install` | first-time setup (venv, npm ci, pre-commit install) |
| `make env` | interactive env-var bootstrap |
| `make dev` | prints backend + frontend dev-server commands |
| `make test` | runs every test suite |
| `make test-backend` / `test-agent` / `test-frontend` | per-area |
| `make lint` | ruff + black --check + tsc + ESLint + Prettier |
| `make format` | auto-fix everything |
| `make ci` | the same checks GitHub Actions runs |

## Pre-commit

Installed by `make install`. Runs on every `git commit`:

- `ruff` (Python lint + auto-fix)
- `ruff-format` (Python format)
- `black` (Python format — same version as CI: 26.3.1)
- `gitleaks` (secret scanning, custom rules in [`.gitleaks.toml`](../.gitleaks.toml))
- `lint-staged` on staged JS/TS/CSS (Prettier + ESLint)
- standard hygiene: trailing-whitespace, end-of-file, check-yaml, check-toml, large-files, merge-conflict markers

**Tests do NOT run in pre-commit.** Too slow. CI catches them.

If a hook fails, fix the issue and re-commit. **Never `--no-verify`** unless explicitly whitelisted (currently: line-ending false-positive on Windows; tracked).

## CI / E2E

### CI (`.github/workflows/ci.yml`)
Triggered on push to `master` or `dev`. Three parallel jobs:

- **Backend** — ruff + black --check + pytest (79 unit tests).
- **Agent** — pytest (14 unit tests).
- **Frontend** — tsc + ESLint + Prettier --check + vitest.

A `ci-complete` aggregator job depends on all three with `if: always()`; it's the single check protected on master. Path-filtered jobs that skip count as success.

### E2E (`.github/workflows/e2e.yml`)
Same triggers. Two sequential jobs:

- **Backend integration** — httpx → deployed FastAPI. Hits `cms-backend-roman.vercel.app`. Marker filter:
  - dev push: `-m "integration and not deployed_state"` (skips tests that assert behavior of the *just-pushed* code, since prod hasn't deployed it yet).
  - master push: full `-m integration` after a 4-min `/health` poll + 60s edge-cache cushion.
- **Frontend E2E** — Playwright → deployed Next.js. 1 worker, fullyParallel: false (shared seed user/project; lock TEST-001).

An `e2e-complete` aggregator job is the single check protected.

### Status checks on master
Branch protection requires:
- `ci-complete`
- `e2e-complete`

Any other failing/skipped sub-job is invisible to protection — only the aggregator's red/green matters.

## Vercel

| Project | URL | Auto-deploys from |
|---|---|---|
| `cms-backend-roman` | https://cms-backend-roman.vercel.app | `master` |
| `cms-frontend-roman` | https://roman-technologies.dev (custom domain) | `master` |
| Per-client | `<slug>.vercel.app` | per-project; managed by `agents/CMS Connector - Website` |

Preview deploys (any branch other than master) are also created for backend + frontend. Useful for ad-hoc QA. After PR-4, E2E will target the dev branch's preview URLs instead of prod.

## Test markers (pytest)

| Marker | Where it runs | What it tests |
|---|---|---|
| (none) | every push, ms each | pure unit logic, mocks |
| `integration` | every push (E2E job) | deployed backend, real network, no mocks |
| `deployed_state` | master push only, post-deploy | asserts the *freshly-deployed* code matches expectations (security headers, rate-limit thresholds, RLS policies) |

If you write a test that checks "the version of the code I just pushed is running" — mark it `deployed_state`. CI on dev will skip it; CI on master will run it after the deploy gate.

## Admin-bypass runbook (master push when CI/E2E gate fails)

Branch protection on `master` requires `ci-complete` + `e2e-complete` green on the dev tip. Sometimes (e.g. the `deployed_state` catch-22) a dev push can't satisfy them until master deploy lands. Procedure:

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

1. Pull the Vercel runtime logs (frontend + backend) for the deploy window.
2. If the cause is the latest deploy: roll back via Vercel dashboard (or `vercel rollback` if CLI is configured).
3. Fix on `dev`, push, re-merge.
4. Document in [`docs/SECURITY.md`](./SECURITY.md) if user data was potentially affected.

The post-mortem template lives at `docs/superpowers/post-mortems/YYYY-MM-DD-<slug>.md`.

## Roadmap

The lifecycle described above is the **current** state (post-PR-1/2/3). Open items that further reduce friction without losing safety:

- **PR-4** — E2E targets the dev-branch Vercel preview URL (auto-discovered via `deployment_status` event). Eliminates the catch-22 where `deployed_state` tests can only pass after merge.
- **PR-5** — Auto-merge dev → master on every green push (replacing the weekly cron).
- **PR-6** — Post-deploy smoke probe + auto-rollback on master.
- **PR-7** — Dependabot auto-merge for patch + minor bumps when CI green.
- **PR-8** — Coverage (Codecov) + mypy seed + CodeQL workflow.

After PR-4 + PR-5: average code-to-prod latency drops from "next scheduled cron" to "~6-10 minutes from push". Manual interventions disappear unless something genuinely breaks.
