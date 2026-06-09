# Onboarding — How code reaches production here

Welcome. This doc gets you productive in 30 minutes. No CI jargon, no acronym soup. If you want the full reference, read [`DEVELOPMENT.md`](./DEVELOPMENT.md) afterwards.

## The big picture

```
        you edit code on a feature branch
                       │
                       ▼
            git push origin <your-branch>
                       │
                       ▼
        you merge feature → dev, push
                       │
        ┌──────────────┴──────────────┐
        │  No CI runs on dev. Vercel  │
        │  auto-deploys a dev preview │
        │  for frontend + backend.    │
        └──────────────┬──────────────┘
                       │ preview looks good?
                       ▼
        run "Promote dev → main" (Actions tab)
                       │
        ┌──────────────┴──────────────┐
        │  Gates: frontend lint+build │
        │  · backend deps+ruff+compile│
        │  · gitleaks secret scan     │
        └──────────────┬──────────────┘
                       │ all gates green?
              ┌────────┴────────┐
              │                 │
            green             any gate fails
              │                 │
   main fast-forwards     Aborted. main
   to dev; Vercel prod    untouched. Fix on
   deploy hooks fire      dev, re-run.
   (frontend + backend).
              │
              ▼
       Done. Live now.
```

You never click "deploy" for previews — pushing to `dev` is enough. Going to production is one deliberate click: run the **Promote dev → main** Action and, if every gate passes, your work is live a couple of minutes later.

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
# No CI runs on push. Feature branches are just for sharing/backup.

# 7. When the feature is done — merge into dev
git checkout dev
git pull               # pull anything Stefan landed while you were working
git merge fix/something-short-and-clear
git push origin dev
# Pushing to dev runs NO checks. Vercel auto-deploys a dev preview
# for frontend (roman-technologies-git-dev-*.vercel.app) and backend
# (cms-backend-roman-git-dev-*.vercel.app). Test there. When it's
# ready for production, run the "Promote dev → main" Action (see below).

# 8. Delete the merged branch (optional, keeps things tidy)
git branch -d fix/something-short-and-clear
git push origin --delete fix/something-short-and-clear
```

## Promoting dev → production

Production deploys are manual and deliberate — there is no scheduled auto-merge.

1. Verify the change on the dev preview URLs (frontend + backend) Vercel built from your `dev` push.
2. Go to the **Actions** tab → **Promote dev → main** → **Run workflow**.
3. The action runs three gates, in order:
   - **Frontend** — `npm ci && npm run lint && npm run build`
   - **Backend** — `pip install --require-hashes -r requirements.lock` + `ruff check` + `python -m compileall`
   - **Secrets** — a `gitleaks` scan for leaked tokens
4. If every gate passes, the action fast-forwards `main` to `dev` and fires the Vercel production deploy hooks for both frontend (roman-technologies.dev) and backend (cms-backend-roman.vercel.app). If any gate fails, it aborts and `main` is left untouched — fix it on `dev` and re-run.

You never push to `main` yourself: it's protected, and only the promote action (using a `PROMOTE_TOKEN` PAT) writes to it.

## Things you should never do

- **Push directly to `main`.** `main` is protected and only the Promote action writes to it. Push to `dev` and promote.
- **Force-push `dev`.** Other people's work might be there. Force-pushing rewrites history and loses commits silently.
- **Skip pre-commit hooks** with `git commit --no-verify`. They exist for a reason — the most common cause is a leaked API key. If a hook misbehaves, fix the hook, don't bypass it.
- **Edit `main` branch protection** without telling Stefan. The settings are tuned so only the Promote action can write to it.
- **Apply Supabase migrations on a whim.** SQL files in `backend/migrations/` need Stefan's review and a human applies them via the Supabase dashboard. The CMS code does not auto-run them.

## Things you should always do

- **Write tests** for non-trivial logic. Run them locally with `make ci` before you push — there is no CI on push to catch regressions for you.
- **Read the existing patterns** in the file you're editing. The codebase has a consistent style; match it.
- **Write commit messages that explain WHY**, not what. The diff already shows what.
- **Run the local checks before promoting.** The Promote action lints and builds both apps and scans for secrets; catching a failure locally (`make ci`) saves you a round-trip.

## When you're stuck

- **The Promote action failed and you don't know why** → Click the failing run in the Actions tab, scroll to the red ✗. Most failures fall into three buckets:
  - **Frontend lint / build** — run `make format` (or `npm run lint`/`npm run build` in `frontend/`), fix, push to `dev`, re-run.
  - **Backend ruff / compile** — your change broke `ruff check` or `python -m compileall`. Read the error, fix on `dev`, re-run.
  - **gitleaks** — the scan found a secret in the diff. Remove it, rotate the leaked credential, and re-run.
- **The dev preview looks wrong but the code is right** → Hard refresh (Ctrl-Shift-R). If still wrong, the Vercel build may have used a stale env var. Stefan handles env vars in the Vercel dashboard.
- **Heads up: dev and prod share one Supabase database** (no dev DB isolation yet), so data changes on the dev preview hit production data. Be careful with destructive operations.

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

## Slack Issue Notifications

The backend posts to `#issues-websites` when a client submits an issue and when an admin marks it resolved.

### One-time setup

1. Go to https://api.slack.com/apps → **Create New App** → **From scratch**.
2. Name: `CMS Issues Bot`. Workspace: your Slack workspace.
3. **OAuth & Permissions** → **Bot Token Scopes** → add `chat:write`.
4. **Install to Workspace** → approve.
5. Copy the **Bot User OAuth Token** (starts with `xoxb-...`) into the backend env as `SLACK_BOT_TOKEN`.
6. In Slack desktop, right-click `#issues-websites` → **View channel details** → copy the **Channel ID** (e.g. `C0123ABCDEF`). Put it in `SLACK_ISSUES_CHANNEL_ID`.
7. Inside `#issues-websites`, run `/invite @CMS Issues Bot`. The bot must be a channel member to post.

### Disabled mode

Leaving `SLACK_BOT_TOKEN` or `SLACK_ISSUES_CHANNEL_ID` unset disables notifications silently — useful for local dev and CI. The service logs `slack_notify disabled` at INFO and never raises.

## Slack Approval & Revision (S1.5)

S1 posts notifications; S1.5 listens for Stefan's response in `#issues-websites`. A ✅ reaction on a resolved-issue Slack message merges `cms-preview → master` of the client repo (triggering a Vercel production deploy) and emails the client. A threaded text reply (≥5 chars) reverts the issue to `in_progress` and stores Stefan's feedback for later S3 use.

### One-time additions to the Slack app

1. https://api.slack.com/apps → CMS Issues Bot → **OAuth & Permissions** → Bot Token Scopes → add `reactions:read` and `channels:history`.
2. Click **Reinstall to Workspace** → approve. Copy the new `xoxb-...` token (the old one is revoked). Update `SLACK_BOT_TOKEN` in `backend/.env` and Vercel envs.
3. **Basic Information** → App Credentials → copy the **Signing Secret** → set as `SLACK_SIGNING_SECRET`.
4. **Event Subscriptions** → Enable → Request URL: `https://cms-backend-roman.vercel.app/slack/events` (deploy the backend with the new router first, otherwise Slack's verification ping fails). Subscribe to bot events: `reaction_added`, `message.channels`. Save.

### One-time GitHub PAT

Reuse the CMS Connector agent's PAT (`repo` scope) or create a new one at https://github.com/settings/tokens. Set as `GITHUB_TOKEN` env var (backend + Vercel).

### Slack user IDs

In Slack desktop, click your profile → **Copy member ID** for `SLACK_APPROVER_USER_ID`. For `SLACK_BOT_USER_ID`, in the Slack app dashboard go to OAuth & Permissions and copy the Bot User ID shown near the bot user setting.

## Glossary in plain words

- **dev** = the integration branch. Pushing here runs no checks and gives you a Vercel preview of frontend + backend.
- **main** = the production branch. Protected; only the Promote action writes to it.
- **Promote dev → main** = the manual GitHub Action that gates (frontend lint+build, backend deps+ruff+compile, gitleaks) and, if green, fast-forwards `main` to `dev` and fires the Vercel production deploy hooks.
- **gitleaks** = the secret-scanning gate in the Promote action — it blocks the promote if it finds a token or key in the diff.
- **CodeQL** = a security code-scan that runs on its own weekly schedule (not on push); findings show up under the repo's Security → Code scanning tab.
- **Solver Agent** = a kept GitHub Actions workflow that picks up issues (on dispatch + hourly); unrelated to the promote pipeline.

## The contract

- We move fast because the pipeline is reliable.
- The pipeline is reliable because we don't bypass it.
- We don't bypass it because we trust each other to write tests and read failures.

If you ever feel like the pipeline is in your way, say so. The fix is to improve the pipeline, not to ship around it.

Welcome aboard.
