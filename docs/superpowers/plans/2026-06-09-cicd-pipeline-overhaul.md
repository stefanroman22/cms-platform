# CI/CD Pipeline Overhaul Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the auto-gated `dev→master` pipeline with: free pushes to `dev` (no checks, auto dev-preview), a single manual `promote.yml` that gates on build+secret-scan and fast-forwards production, `master` renamed to `main`, Dependabot removed, Solver Agent + weekly CodeQL kept.

**Architecture:** All CI/merge/smoke workflows deleted; one `workflow_dispatch` promote job is the only path to production. `main` is protected so only that job (via a `PROMOTE_TOKEN` PAT bypass) can write it; the job fires Vercel production deploy hooks for the frontend and backend. `dev` and `main` are kept identical-at-rest (promote only ever fast-forwards `main` to `dev`).

**Tech Stack:** GitHub Actions, GitHub REST API (`gh`), Vercel (two projects: `roman-technologies` FE `prj_Z4tNbPa89oyd0WCRkqL9rIWntfLU`, `cms-backend-roman` BE `prj_uqWx3NgmJXeVMAwiSci4C2pYTxM8`, team `team_tG5MNAl15KS2zPlAvmZJTl9y`), gitleaks, Next.js 16, FastAPI.

**Reference spec:** `docs/superpowers/specs/2026-06-09-cicd-pipeline-overhaul-design.md`

**Operator prerequisites (must exist before Task 9 & Task 12):**
- `PROMOTE_TOKEN` repo secret — fine-grained PAT, `cms-platform` only, Contents: read+write.
- `FE_PROD_DEPLOY_HOOK` repo secret — existing `deploy-master` hook (re-point to `main` in Task 8).
- `BE_PROD_DEPLOY_HOOK` repo secret — created in Task 8.

---

### Task 0: Pre-flight — capture current state

**Files:** none (read-only).

- [ ] **Step 1: Snapshot branches, protection, Vercel prod branch, PR list**

Run:
```bash
cd "CMS - websites"
git fetch origin --quiet
echo "dev=$(git rev-parse origin/dev)  master=$(git rev-parse origin/master)"
git merge-base --is-ancestor origin/master origin/dev && echo "master ANCESTOR of dev (FF dev->master OK)" || echo "DIVERGED (master has commits dev lacks)"
gh api repos/stefanroman22/cms-platform --jq '.default_branch'
gh api repos/stefanroman22/cms-platform/branches/master/protection --jq '.required_status_checks.contexts' 2>&1
gh pr list --repo stefanroman22/cms-platform --state open --json number --jq 'length'
```
Expected: prints the two SHAs, divergence verdict, `master`, the two gate contexts, and `31` (PR count). **Record these.**

- [ ] **Step 2: Confirm operator prerequisite present**

Run: `gh secret list --repo stefanroman22/cms-platform | grep -i promote || echo "PROMOTE_TOKEN MISSING"`
Expected: `PROMOTE_TOKEN` listed. If missing, STOP and have the operator create it (spec §Prerequisites).

---

### Task 1: Reconcile `dev` and `master` to a common base

**Why:** the promote model fast-forwards `main` from `dev`; that only works if `dev` is a descendant of `main`. Today `master` (cfe39e1, the PR-#58 merge commit) is ahead of `dev`. We make `dev` the source of truth by fast-forwarding `dev` up to `master`, so `dev ⊇ master`, then all new work (the cleanup commit) sits on top of `dev`.

**Files:** none (git refs).

- [ ] **Step 1: Fast-forward `dev` to include `master`'s tip**

Run (only if Task 0 Step 1 reported DIVERGED):
```bash
git push origin origin/master:refs/heads/dev
```
If `dev` is not protected this succeeds (dev advances to master's SHA, no content lost since master ⊇ dev content). If rejected as non-FF, STOP and inspect — do not force without confirming nothing unique is on `dev`.

- [ ] **Step 2: Verify**

Run: `git fetch origin --quiet && git merge-base --is-ancestor origin/master origin/dev && echo "OK: master is ancestor of dev"`
Expected: `OK: master is ancestor of dev`.

---

### Task 2: Author workflow changes on a clean cleanup branch off `dev`

**Files:**
- Delete: `.github/workflows/ci.yml`, `.github/workflows/e2e.yml`, `.github/workflows/auto-merge-dev-to-master.yml`, `.github/workflows/post-deploy-smoke.yml`, `.github/workflows/scraper-ci.yml`, `.github/workflows/dependabot-auto-merge.yml`
- Delete: `.github/dependabot.yml`
- Modify: `.github/workflows/codeql.yml` (strip push trigger)
- Modify: `.github/workflows/solver-agent.yml` (master→main refs)
- Create: `.github/workflows/promote.yml`

- [ ] **Step 1: Create a cleanup branch off the reconciled `dev`**

```bash
git fetch origin --quiet
git checkout -B chore/cicd-overhaul origin/dev
```

- [ ] **Step 2: Delete the six workflows + dependabot config**

```bash
git rm .github/workflows/ci.yml .github/workflows/e2e.yml \
       .github/workflows/auto-merge-dev-to-master.yml \
       .github/workflows/post-deploy-smoke.yml \
       .github/workflows/scraper-ci.yml \
       .github/workflows/dependabot-auto-merge.yml \
       .github/dependabot.yml
```

- [ ] **Step 3: Trim `codeql.yml` to schedule-only**

Replace the `on:` block (lines 15–20) so the `push` trigger is removed:
```yaml
on:
  schedule:
    - cron: "0 3 * * 0"
  workflow_dispatch:
```
Leave the rest of the file unchanged.

- [ ] **Step 4: Repoint `solver-agent.yml` master→main**

Run to find refs: `grep -nE "master" .github/workflows/solver-agent.yml`
For each hit, change `master` → `main` (e.g. `--ref master` → `--ref main`, any `branches: [master]`, env defaults). If there are zero hits, no change needed.

- [ ] **Step 5: Create `promote.yml`**

````yaml
# Manual production promotion. Push freely to `dev`; click "Run workflow"
# here when you want dev to become production. Gates on build + secret scan,
# then fast-forwards `main` to `dev` and redeploys both Vercel projects.
name: Promote dev → main

on:
  workflow_dispatch:

concurrency:
  group: promote-to-main
  cancel-in-progress: false

permissions:
  contents: read

jobs:
  promote:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@11bd71901bbe5b1630ceea73d27597364c9af683 # v4.2.2
        with:
          ref: dev
          fetch-depth: 0

      # --- GATE: frontend builds + lints ---
      - uses: actions/setup-node@49933ea5288caeca8642d1e84afbd3f7d6820020 # v4.4.0
        with:
          node-version-file: frontend/.nvmrc
          cache: npm
          cache-dependency-path: frontend/package-lock.json
      - name: Frontend lint + typecheck + build
        working-directory: frontend
        run: |
          npm ci
          npm run lint
          npx tsc --noEmit
          npm run build

      # --- GATE: backend deps install + syntax ---
      - uses: actions/setup-python@a26af69be951a213d495a4c3e4e4022e16d87065 # v5.6.0
        with:
          python-version: "3.13"
      - name: Backend install + ruff + syntax
        working-directory: backend
        run: |
          pip install --require-hashes -r requirements.lock
          pip install ruff
          ruff check .
          python -m compileall -q auth_service

      # --- GATE: secret scan ---
      - name: Secret scan (gitleaks)
        uses: gitleaks/gitleaks-action@cb7149a9b57195b609c63e8518d2c6056677d2d0 # v2.3.9
        env:
          GITLEAKS_CONFIG: ${{ github.workspace }}/.gitleaks.toml

      # --- PROMOTE: fast-forward main = dev ---
      - name: Fast-forward main to dev
        env:
          PROMOTE_TOKEN: ${{ secrets.PROMOTE_TOKEN }}
        run: |
          git push "https://x-access-token:${PROMOTE_TOKEN}@github.com/${{ github.repository }}.git" \
            origin/dev:refs/heads/main

      # --- DEPLOY: fire both production deploy hooks ---
      - name: Redeploy production (frontend + backend)
        env:
          FE_HOOK: ${{ secrets.FE_PROD_DEPLOY_HOOK }}
          BE_HOOK: ${{ secrets.BE_PROD_DEPLOY_HOOK }}
        run: |
          curl -fsS -X POST "$FE_HOOK" && echo "✅ frontend prod deploy triggered"
          curl -fsS -X POST "$BE_HOOK" && echo "✅ backend prod deploy triggered"
````

Note: `origin/dev:refs/heads/main` works because checkout fetched full history; the push source is the fetched remote-tracking ref. If the runner's git lacks `origin/dev`, substitute `HEAD:refs/heads/main` (HEAD is already `dev`).

- [ ] **Step 6: Add a `.gitleaks.toml` allowlist for known test fixtures**

Create `.gitleaks.toml` (prevents false positives on E2E/test placeholder secrets):
```toml
title = "cms-platform gitleaks config"
[extend]
useDefault = true
[allowlist]
description = "Test fixtures and docs, not real secrets"
paths = [
  '''e2e/.*''',
  '''.*/tests?/.*''',
  '''scripts/seed_e2e\.py''',
  '''docs/.*''',
]
```

- [ ] **Step 7: Verify the workflow set locally**

Run: `ls .github/workflows/`
Expected: only `codeql.yml`, `solver-agent.yml`, `promote.yml` remain.

---

### Task 3: Docs / agents / memory sweep (parallel)

**Files:** all repo files referencing `master` / the old pipeline, plus the auto-memory at `C:\Users\stefa\.claude\projects\c--Users-stefa--gemini-antigravity-scratch-CMS---websites\memory\`.

- [ ] **Step 1: Enumerate the surface**

Run: `grep -rniE "master|auto-merge|dev→master|dev-to-master|CI complete \(gate\)|E2E complete \(gate\)" --include=*.md --include=*.yml . | grep -viE "docs/superpowers/(specs|plans)/2026-0[0-5]" | cut -d: -f1 | sort -u`
Record the file list. **Exclude** client-repo branch semantics (`cms-preview`, client `main`) — those are unrelated.

- [ ] **Step 2: Run the rewrite as a Workflow (ultracode)**

Dispatch one subagent per doc cluster to update `master`→`main` and replace the old-pipeline description (CI/E2E gates, auto-merge dev→master, post-deploy smoke) with the new flow (free dev pushes → manual `promote.yml` → main; Vercel dev preview + prod hooks). Clusters: `docs/` (DEVELOPMENT, ONBOARDING, SECURITY, README), agent `AGENTS.md` files, and the memory directory (`reference_dev_lifecycle.md`, `MEMORY.md`, plus any file the grep surfaced). Each agent edits only its cluster and returns the list of files changed + lines touched. A final critic agent re-greps for stragglers.

- [ ] **Step 3: Verify no platform `master` references remain**

Run the Step 1 grep again. Expected: only intentional historical references inside dated spec/plan files (and client-repo `main` mentions). Everything describing the live platform pipeline says `main` + the new flow.

---

### Task 4: Land the cleanup on `dev`

**Files:** none new.

- [ ] **Step 1: Commit (operator authorizes)**

```bash
git add -A
git commit -m "chore(ci): tear down dev/master auto-pipeline; add manual promote.yml; trim CodeQL to weekly; remove Dependabot; master→main docs sweep"
```

- [ ] **Step 2: Merge cleanup branch into `dev` and push**

```bash
git push origin chore/cicd-overhaul:dev
```

- [ ] **Step 3: Verify no workflows ran for this push**

Run: `gh run list --repo stefanroman22/cms-platform --branch dev --limit 5`
Expected: no new CI/E2E/CodeQL runs from this push (CodeQL no longer triggers on push; others deleted). CodeQL's deletion-from-push takes effect because the pushed tree no longer has those triggers.

---

### Task 5: Remove `master` branch protection

**Files:** none (GitHub API).

- [ ] **Step 1: Delete the old protection (so the required gates stop blocking merges)**

```bash
gh api -X DELETE repos/stefanroman22/cms-platform/branches/master/protection
```
Expected: HTTP 204.

- [ ] **Step 2: Verify**

Run: `gh api repos/stefanroman22/cms-platform/branches/master/protection 2>&1 | head -1`
Expected: `Branch not protected` (404).

---

### Task 6: Sync `master` to `dev`

**Files:** none (git refs).

- [ ] **Step 1: Fast-forward `master` to `dev`**

```bash
git fetch origin --quiet
git push origin origin/dev:refs/heads/master
```
Expected: FF success (dev = master + cleanup commit ⇒ FF). Now `master == dev`.

---

### Task 7: Rename `master` → `main`

**Files:** none (GitHub API).

- [ ] **Step 1: Rename the branch**

```bash
gh api -X POST repos/stefanroman22/cms-platform/branches/master/rename -f new_name=main
```
Expected: JSON for the `main` branch. GitHub auto-updates the default branch and retargets any open PRs.

- [ ] **Step 2: Verify default branch + branch exists**

```bash
gh api repos/stefanroman22/cms-platform --jq '.default_branch'   # expect: main
gh api repos/stefanroman22/cms-platform/branches/main --jq '.name' # expect: main
```

---

### Task 8: Vercel — production branch, hooks, dev preview wiring

**Files:** none (Vercel dashboard / operator).

- [ ] **Step 1: Switch Production Branch → `main` on BOTH projects**

Operator: Vercel → `roman-technologies` → Settings → Git → Production Branch → set `main`. Repeat for `cms-backend-roman`. (Confirm to agent when done.)

- [ ] **Step 2: Re-point the frontend prod deploy hook to `main`**

The existing `deploy-master` hook targets `master`. Operator: Vercel → `roman-technologies` → Settings → Git → Deploy Hooks → create a new hook `deploy-main` (branch `main`); save its URL as repo secret `FE_PROD_DEPLOY_HOOK` (replacing the old). Run:
`gh secret set FE_PROD_DEPLOY_HOOK --repo stefanroman22/cms-platform --body "<frontend main hook url>"`

- [ ] **Step 3: Create the backend prod deploy hook**

Operator: Vercel → `cms-backend-roman` → Settings → Git → Deploy Hooks → create `deploy-main` (branch `main`); then:
`gh secret set BE_PROD_DEPLOY_HOOK --repo stefanroman22/cms-platform --body "<backend main hook url>"`

- [ ] **Step 4: Point frontend Preview env at backend dev alias**

Operator: Vercel → `roman-technologies` → Settings → Environment Variables → the CMS/API base var → add/edit a **Preview**-scoped value = `https://cms-backend-roman-git-dev-stefanromanpers-5412s-projects.vercel.app` (so dev FE calls dev BE). Leave Production value untouched.

- [ ] **Step 5: Verify dev previews auto-deploy**

Run: `git commit --allow-empty -m "chore: dev preview smoke" && git push origin HEAD:dev`
Then check both projects produced a new `…-git-dev-…` deployment:
`mcp__vercel__list_deployments` for each project → newest entry has `githubCommitRef: dev`, `state: READY`.

---

### Task 9: Protect `main` (promote-action-only writes)

**Files:** none (GitHub API / ruleset).

- [ ] **Step 1: Create a ruleset blocking direct pushes, bypass = the PROMOTE_TOKEN identity**

On a personal repo, use a repository ruleset targeting `main` with rules `non_fast_forward` (block force) + `deletion` + `update`/required-PR set so non-bypass actors can't push, and a `bypass_actors` entry for the token's owner (Repository admin role id 5) — since the PAT runs as `stefanroman22` (the owner), owner-bypass lets `promote.yml` push while still surfacing "protected" to casual pushes via the default GitHub UI guardrails. Create via:
```bash
gh api -X POST repos/stefanroman22/cms-platform/rulesets \
  -f name='main-promote-only' -f target=branch -f enforcement=active \
  -f 'conditions[ref_name][include][]=refs/heads/main' \
  -f 'rules[][type]=deletion' \
  -f 'rules[][type]=non_fast_forward' \
  -f 'bypass_actors[][actor_id]=5' -f 'bypass_actors[][actor_type]=RepositoryRole' -f 'bypass_actors[][bypass_mode]=always'
```
**Validate the exact ruleset shape interactively** — the personal-repo ruleset API is finicky; confirm with a dry-run that (a) a direct human push to `main` is blocked and (b) `promote.yml` (PAT) can still fast-forward. Adjust rules if the dry-run shows otherwise.

- [ ] **Step 2: Verify**

Run: `gh api repos/stefanroman22/cms-platform/rulesets --jq '.[].name'`
Expected: `main-promote-only` listed.

---

### Task 10: Reset `dev` to `main` (identical at rest)

**Files:** none (git refs).

- [ ] **Step 1: Fast-forward/sync dev to main**

```bash
git fetch origin --quiet
git push origin origin/main:refs/heads/dev
```
Expected: `dev == main`. (After Task 6+7, `main` already equals the old `dev`+cleanup, so this is a no-op or trivial FF — confirms parity.)

---

### Task 11: Dependabot teardown + branch cleanup

**Files:** none (GitHub API). (`dependabot.yml` + `dependabot-auto-merge.yml` already deleted in Task 2.)

- [ ] **Step 1: Disable Dependabot security + vulnerability features**

```bash
gh api -X DELETE repos/stefanroman22/cms-platform/automated-security-fixes
gh api -X DELETE repos/stefanroman22/cms-platform/vulnerability-alerts
```
Expected: HTTP 204 each.

- [ ] **Step 2: Close all open Dependabot PRs and delete their branches**

```bash
for n in $(gh pr list --repo stefanroman22/cms-platform --state open --author "app/dependabot" --json number --jq '.[].number'); do
  gh pr close "$n" --repo stefanroman22/cms-platform --delete-branch
done
```

- [ ] **Step 3: Verify zero Dependabot PRs / branches remain**

```bash
gh pr list --repo stefanroman22/cms-platform --state open --author "app/dependabot" --json number --jq 'length'   # expect 0
git ls-remote --heads origin 'dependabot/*' | wc -l   # expect 0
```

---

### Task 12: End-to-end smoke

**Files:** none.

- [ ] **Step 1: Confirm free dev push (no checks)**

```bash
git commit --allow-empty -m "chore: smoke dev no-checks" && git push origin HEAD:dev
gh run list --repo stefanroman22/cms-platform --branch dev --limit 3
```
Expected: dev preview redeploys (FE+BE); no CI/E2E/CodeQL runs.

- [ ] **Step 2: Run the promote action**

```bash
gh workflow run "Promote dev → main" --repo stefanroman22/cms-platform --ref main
gh run watch "$(gh run list --repo stefanroman22/cms-platform --workflow 'Promote dev → main' --limit 1 --json databaseId --jq '.[0].databaseId')"
```
Expected: gate steps pass; `main` fast-forwards to `dev`; both deploy hooks fire.

- [ ] **Step 3: Confirm production updated (both projects)**

`mcp__vercel__get_deployment` for `roman-technologies.dev` and `cms-backend-roman.vercel.app` → `githubCommitRef: main`, SHA == `origin/main`, `target: production`, `READY`.

---

### Task 13: Final audit + spec/memory close-out

- [ ] **Step 1: Repo-wide master audit**

Run: `grep -rniE "\bmaster\b" --include=*.md --include=*.yml . | grep -viE "docs/superpowers/(specs|plans)/" `
Expected: no live-pipeline references to `master` (only dated historical docs / client-repo notes).

- [ ] **Step 2: Update memory**

Add/refresh a memory entry recording the new pipeline (dev free-push → manual `promote.yml` → `main`; Dependabot off; Vercel dev preview + prod hooks; `PROMOTE_TOKEN` + the two deploy-hook secrets) and mark `reference_dev_lifecycle.md` updated. Update the design spec `Status: Implemented`.

---

## Self-Review

**Spec coverage:** W1 workflow teardown → Task 2; W2 promote.yml → Task 2 Step 5; W3 rename + Vercel prod branch → Tasks 7–8; W4 main protection → Task 9; W5 Dependabot → Tasks 2+11; W6 Vercel dev/prod wiring → Task 8; W7 docs/memory sweep → Tasks 3+13. Prerequisites → header + Task 0 Step 2 / Task 8. Sequencing (remove protection before sync; rename before Vercel prod-branch; reconcile before promote) → Tasks 1,5,6,7,10. All spec sections mapped.

**Placeholder scan:** Two flagged investigation points remain by necessity and are marked "validate interactively": the exact `main` ruleset shape (Task 9) and the gitleaks allowlist tuning (Task 2 Step 6) — both are environment-dependent and must be confirmed against the live personal repo, not guessable in advance. All file paths, commands, and the full `promote.yml`/`.gitleaks.toml` content are concrete.

**Type/consistency:** Secret names consistent (`PROMOTE_TOKEN`, `FE_PROD_DEPLOY_HOOK`, `BE_PROD_DEPLOY_HOOK`) across header, `promote.yml`, and Task 8. Project IDs match the spec. Branch flow consistent: reconcile dev⊇master → cleanup on dev → FF master=dev → rename → dev==main.
