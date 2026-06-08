# Phase 2 — Clone

**Goal:** Clone the client repo at `cms-preview` HEAD and record the current SHA as a diff-anchor for revision-feedback retries.

**Inputs:**
- `/tmp/issue.json` (from Phase 1) — includes `project.github_repo`, `project.repo_branch` (= `cms-preview`).
- `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. Read repo + staging branch name from `/tmp/issue.json`.
2. `git clone --branch <repo_branch> --depth 50 <auth-url> ./client-repo` — clones `cms-preview` at its current HEAD.
3. Configure git user: `Solver Agent <solver@roman-technologies.dev>`.
4. Write `git rev-parse HEAD` (inside `./client-repo`) to `PREV_SHA_PATH` (`/tmp/prev-solver-sha`). This SHA is the diff-anchor used in revision-feedback retries so the next attempt can see exactly what the prior attempt changed. With the staging-branch model, prior attempts live in branch history — no orphan-recovery hack needed.

**Outputs:**
- `./client-repo/` at `cms-preview` HEAD, with that branch checked out.
- `/tmp/prev-solver-sha` — SHA of `cms-preview` at clone time.

**Failure messages:**
- 401/403 on clone → PAT scope drift; surface "git clone failed: <code>".
- 404 on clone → repo missing or `cms-preview` branch does not exist yet; surface "Repo not found".
