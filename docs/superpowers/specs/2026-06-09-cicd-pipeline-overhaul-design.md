# CI/CD Pipeline Overhaul — `dev` → manual promote → `main` — Design

**Date:** 2026-06-09
**Status:** Implemented + verified end-to-end 2026-06-09
**Repo:** `stefanroman22/cms-platform` (personal/user-owned, public)

## Goal

Replace the current auto-gated `dev → master` pipeline with a simple, manual,
operator-controlled flow:

- **`dev` is the free workspace** — pushing to `dev` runs **no** checks or
  workflows. Vercel still auto-deploys a `dev` preview URL (frontend + backend).
- **Promotion to production is one manual button** — a `workflow_dispatch`
  action that gates on build + secret-scan, then fast-forwards `main` to `dev`
  and redeploys production (frontend + backend).
- **`master` is renamed to `main`** everywhere (GitHub, Vercel, docs, agents,
  memory).
- **Dependabot is removed entirely** and its 31 open PRs/branches cleaned up.
- The **Solver Agent** workflow (tick + schedule) is the only retained
  automation. **CodeQL** is retained as a weekly-scheduled-only security scan.

## Locked decisions (from brainstorming)

| Decision | Choice |
|---|---|
| Checks on `dev` push | **None** |
| Checks on `dev`→`main` merge | **None automatic** — only the manual promote gate |
| Dependabot | **Disabled fully** (config + auto-merge workflow + GitHub security/version updates), close all 31 PRs |
| `main` write model | **Protected** — only the promote action writes to `main` (humans blocked) |
| Dev/prod isolation | **URLs only** — dev and prod share the same Supabase DB (dev DB isolation deferred, out of scope) |
| CodeQL | **Keep, weekly-scheduled only** (strip `push` triggers) |
| Solver Agent | **Keep** (tick via `repository_dispatch` + schedule + dispatch) |

## End-state architecture

```
push to dev ──▶ (zero checks) ──▶ Vercel auto-deploys dev preview
                                   • FE  roman-technologies-git-dev-*.vercel.app
                                   • BE  cms-backend-roman-git-dev-*.vercel.app
                                   (FE dev preview points at BE dev alias; shared prod Supabase)

operator clicks "Promote dev → main" (Actions › Run workflow)
   │
   ├─ GATE (all blocking; fail ⇒ abort, main untouched):
   │    FE:  npm ci && npm run lint && tsc --noEmit && npm run build
   │    BE:  pip install --require-hashes -r requirements.lock && ruff check
   │         && python -c "import auth_service.main"
   │    SECRETS: gitleaks detect over the working tree
   │
   ├─ fast-forward main = dev   (push via PROMOTE_TOKEN, the only allowed writer)
   │
   └─ POST both Vercel production deploy hooks  (FE + BE redeploy deterministically)

retained: Solver Agent (tick + schedule); CodeQL (weekly Sun 03:00 UTC, no push triggers)
```

## Workstreams

### W1 — Workflow teardown
**Delete:** `ci.yml`, `e2e.yml`, `auto-merge-dev-to-master.yml`,
`post-deploy-smoke.yml`, `scraper-ci.yml`, `dependabot-auto-merge.yml`.
**Trim:** `codeql.yml` — remove the `push: branches: [master, dev]` trigger;
keep `schedule` + `workflow_dispatch`; rename branch refs none needed.
**Keep + repoint:** `solver-agent.yml` — update any `master` ref → `main`
(`gh workflow run … --ref`, checkout refs, env).

### W2 — `promote.yml` (new)
`on: workflow_dispatch` only. Single job:
1. Checkout `dev` (full history).
2. **Gate** steps as above (FE lint/typecheck/build, BE install/ruff/import,
   gitleaks). Any non-zero ⇒ fail the job before touching `main`.
3. Fast-forward: `git push "https://x-access-token:${PROMOTE_TOKEN}@github.com/…" dev:main`
   (fails loudly if not a fast-forward — by design `main` only ever moves
   forward from `dev`).
4. `curl -fsS -X POST "$FE_PROD_DEPLOY_HOOK"` and `"$BE_PROD_DEPLOY_HOOK"`.
Secrets used: `PROMOTE_TOKEN`, `FE_PROD_DEPLOY_HOOK`, `BE_PROD_DEPLOY_HOOK`.

### W3 — Rename `master` → `main`
- GitHub branch rename (auto-retargets open PRs, updates default branch &
  existing protection rule references).
- Set **default branch** = `main` (handled by rename).
- Vercel: set **Production Branch** = `main` on **both** projects
  (`roman-technologies`, `cms-backend-roman`).

### W4 — `main` protection
Personal repo ⇒ use a **ruleset** (or classic protection) that **blocks direct
pushes** to `main` for everyone, with a **bypass** for the `PROMOTE_TOKEN`
identity. No required PR, no required status checks (the gate lives inside
`promote.yml`, not as a branch check). No force-push, no deletion. Exact
mechanism (ruleset bypass actor vs classic) finalized at implementation against
what the personal repo supports.

### W5 — Dependabot teardown
- Delete `.github/dependabot.yml` and `.github/workflows/dependabot-auto-merge.yml`.
- Disable GitHub Dependabot **security updates** (`DELETE /repos/{o}/{r}/automated-security-fixes`)
  and **vulnerability alerts** (`DELETE /repos/{o}/{r}/vulnerability-alerts`).
- Close all 31 open Dependabot PRs and delete their branches.

### W6 — Vercel deploy wiring
- **dev (already works):** confirm both projects auto-deploy `dev` pushes to
  their `*-git-dev-*` aliases. Point the **frontend Preview-env API base** at the
  **backend dev alias** so the dev URL runs dev-FE against dev-BE (shared DB).
- Optional: custom domain `dev.roman-technologies.dev` → FE `dev` branch.
- **prod:** both projects' production deploy hooks are fired by `promote.yml`.
  Frontend hook already exists (`deploy-master`); create the **backend** prod
  deploy hook.

### W7 — Docs / agents / memory sweep
Update every `master`→`main` reference and the new dev→promote→prod flow across
(non-exhaustive): `docs/DEVELOPMENT.md`, `docs/ONBOARDING.md`, `docs/SECURITY.md`,
`README.md`, agent `AGENTS.md` files, any Claude/agent guideline files, and
project **memory** (`reference_dev_lifecycle.md`, `MEMORY.md`, plus any others
mentioning `master`/auto-merge/CI gates). Run as a parallel sweep so nothing is
missed. **Note:** client-repo branch conventions (`cms-preview`, client `main`)
are a *separate* concern and must NOT be conflated with the platform rename.

## Prerequisites the operator must provide

1. **`PROMOTE_TOKEN`** — a fine-grained PAT (owner `stefanroman22`) scoped to
   `cms-platform` with `contents: write` (push) permission, saved as a repo
   secret. Used by `promote.yml` to fast-forward `main` (the only writer).
2. **`BE_PROD_DEPLOY_HOOK`** — a Vercel production deploy hook on
   `cms-backend-roman` (branch `main`), saved as a repo secret. (`FE_PROD_DEPLOY_HOOK`
   = the existing `deploy-master` hook.)

## Sequencing (critical — irreversible steps flagged ⚠)

1. Author all file changes on a working branch: delete W1 workflows, add
   `promote.yml`, trim `codeql.yml`, repoint `solver-agent.yml`, delete
   Dependabot files, run the W7 doc/memory sweep.
2. ⚠ **Remove the `master` required-status-check protection FIRST** (`CI complete (gate)`,
   `E2E complete (gate)`) — otherwise the changes can't land on `master` (the
   gates would be "expected" but never run, blocking the merge).
3. Land the changes on `dev`, then one-time sync to `master` (manual FF/merge by
   operator).
4. ⚠ **Rename** `master` → `main`.
5. Switch Vercel Production Branch → `main` on both projects; create the backend
   prod deploy hook; set the FE Preview API-base env.
6. Apply the W4 `main` protection ruleset with the `PROMOTE_TOKEN` bypass.
7. ⚠ **Dependabot teardown** (W5) + ⚠ **close 31 PRs / delete branches**.
8. Smoke test: push a trivial change to `dev` (confirm no workflows run, dev
   preview updates) → run `promote.yml` (confirm gate runs, `main` fast-forwards,
   both prod deploys fire).

## Risks & rollback

- **Locked-out `main`:** if the ruleset bypass is misconfigured, the promote
  action can't push. Mitigation: validate the bypass with a dry-run before
  deleting the old auto-merge path; keep owner admin bypass available.
- **Lost safety net:** deleting CI/E2E removes all automated correctness checks
  on `dev`. Accepted by design; the promote gate (build + secrets) and CodeQL
  (weekly) are the remaining nets. Tests can be re-added to the promote gate
  later if desired.
- **Rename breakage:** anything still referencing `master` (a missed doc, the
  solver workflow, a Vercel setting) breaks silently. Mitigation: the W7 sweep +
  a post-rename `grep -ri "master"` audit across repo + memory.
- **Secret exposure:** gitleaks in the gate blocks new leaks at promote time; it
  does not retroactively scrub history (out of scope).

## Out of scope (explicitly deferred)

- Isolated **dev Supabase / database** (dev currently shares prod DB).
- Git-history secret scrubbing.
- Re-adding test suites to the promote gate.
- Client-repo (it-global-services / Laurian) pipeline — unaffected by this change.
