# Onboarding — How code reaches production here

Welcome. This doc gets you productive in 30 minutes. No CI jargon, no acronym soup. If you want the full reference, read [`DEVELOPMENT.md`](./DEVELOPMENT.md) afterwards.

## The big picture

```
        you edit code on a feature branch
                       │
                       ▼
            git push origin <your-branch>
                       │
        ┌──────────────┴──────────────┐
        │  GitHub runs CI (lint+      │
        │  unit tests, ~3 min)        │
        └──────────────┬──────────────┘
                       │ green?
                       ▼
        you merge feature → dev, push
                       │
        ┌──────────────┴──────────────┐
        │  CI + E2E + CodeQL run on   │
        │  dev (~6 min total)         │
        └──────────────┬──────────────┘
                       │ both green?
                       ▼
        Robot fast-forwards master to dev
                       │
                       ▼
        Vercel auto-deploys backend + frontend
                       │
                       ▼
        Smoke probes /health, /log-in
                       │
              ┌────────┴────────┐
              │                 │
            green             broken
              │                 │
       Done. Live now.     Auto-rollback +
                           incident issue
                           tags Stefan.
```

You never click "deploy". You never SSH anywhere. You push code, wait ~10 minutes, your work is live.

## Setup (one time)

```bash
# Clone, install, get the dev servers running
git clone https://github.com/stefanroman22/cms-platform.git
cd cms-platform
make install         # creates Python venv, installs all deps, sets up pre-commit hooks
make env             # interactive prompt for required env vars; ask Stefan for secret values
make dev             # prints two commands; run them in two terminals
```

You should see:
- backend on http://127.0.0.1:8001 (FastAPI, hot reload)
- frontend on http://localhost:3000 (Next.js, Turbopack)

Open the frontend, log in with the test credentials Stefan gave you. If anything fails, ping him before continuing.

## Your daily loop

```bash
# 1. Start fresh from the latest dev
git checkout dev
git pull

# 2. Branch off
git checkout -b fix/something-short-and-clear
# branch prefixes we use: fix/, feat/, chore/, feature/
# the prefix doesn't change behavior — it's just a label

# 3. Code. Save.

# 4. (optional but smart) run local checks
make ci

# 5. Commit
git add -p                                # review your changes
git commit -m "feat(workspace): add X"    # the pre-commit hook checks lint + secrets

# 6. Push the feature branch
git push origin fix/something-short-and-clear
# CI runs automatically (lint + unit tests). Watch the run on
# https://github.com/stefanroman22/cms-platform/actions
# Wait for green before continuing.

# 7. When the feature is done — merge into dev
git checkout dev
git pull               # pull anything Stefan landed while you were working
git merge fix/something-short-and-clear
git push origin dev
# Now the full pipeline runs. About 10 minutes later, your
# code is live on roman-technologies.dev.

# 8. Delete the merged branch (optional, keeps things tidy)
git branch -d fix/something-short-and-clear
git push origin --delete fix/something-short-and-clear
```

## Things you should never do

- **Push directly to `master`.** Master is robot-managed. Branch protection blocks you anyway.
- **Force-push `dev`.** Other people's work might be there. Force-pushing rewrites history and loses commits silently.
- **Skip pre-commit hooks** with `git commit --no-verify`. They exist for a reason — the most common cause is a leaked API key. If a hook misbehaves, fix the hook, don't bypass it.
- **Edit `master` branch protection** without telling Stefan. The settings are tuned to make the auto-merge pipeline work.
- **Apply Supabase migrations on a whim.** SQL files in `backend/migrations/` need Stefan's review and a human applies them via the Supabase dashboard. The CMS code does not auto-run them.

## Things you should always do

- **Write tests** for non-trivial logic. The backend has a 60 % coverage floor — if your PR drops it, CI fails. Add a unit test next to your change.
- **Read the existing patterns** in the file you're editing. The codebase has a consistent style; match it.
- **Write commit messages that explain WHY**, not what. The diff already shows what.
- **Mark deployed-state tests** with `pytest.mark.deployed_state` if they assert behaviour of a *freshly-deployed* prod URL. Otherwise CI on dev will fail because prod hasn't deployed your code yet.

## When you're stuck

- **CI is red and you don't know why** → Click the failing job in the Actions tab, scroll to the red ✗. Most failures fall into three buckets:
  - **Lint / format** — run `make format`, commit again.
  - **Unit test** — your change broke something measurable. Read the assertion error.
  - **Coverage drop** — add a test, or document why the new code is genuinely uncoverable (rare).
- **E2E is red on dev push but unit tests pass** → Likely a `deployed_state` test or a flake. Check Stefan / `DEVELOPMENT.md`.
- **Vercel deploy succeeded but the site looks wrong** → Hard refresh (Ctrl-Shift-R). If still wrong, the Vercel build may have used a stale env var. Stefan handles env vars in the Vercel dashboard.

## Where things live

| Want to change… | Look in… |
|---|---|
| API endpoint logic | `backend/auth_service/routers/` |
| Database queries | `backend/auth_service/services/` |
| Dashboard UI | `frontend/src/app/dashboard/` |
| Reusable UI components | `frontend/src/components/` |
| CI / deploy workflows | `.github/workflows/` |
| Database schema (read-only ref) | `backend/migrations/` |
| Public website code | the per-client repo (e.g. `it-global-services`) |

## Glossary in plain words

- **CI** = the GitHub robot that runs tests on every push.
- **E2E** = "end to end" tests — they hit the real deployed site, not mocks.
- **Auto-merge** = the workflow that promotes `dev` to `master` once CI + E2E are green. Sleeps 60 s first to batch your rapid commits into one prod deploy.
- **Smoke test** = a 5-second probe right after deploy that asks "is the prod URL still serving 200s?". If no, it auto-reverts.
- **Aggregator gate** = a fake "summary" CI job that's the only thing branch protection checks. Path-filtered skips don't break it.
- **deployed_state** = a label we put on tests that check prod-state-after-deploy (security headers, rate limits). They only run after the new code is on master + Vercel finishes deploying.

## The contract

- We move fast because the pipeline is reliable.
- The pipeline is reliable because we don't bypass it.
- We don't bypass it because we trust each other to write tests and read failures.

If you ever feel like the pipeline is in your way, say so. The fix is to improve the pipeline, not to ship around it.

Welcome aboard.
