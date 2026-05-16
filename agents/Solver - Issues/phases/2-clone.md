# Phase 2 — Clone + Reset

**Goal:** Clone the client repo and reset the working tree to the production branch HEAD, locally tracked as `cms-preview`.

**Inputs:**
- `/tmp/issue.json` (from Phase 1) — includes `project.github_repo`, `project.repo_branch` (= `cms-preview`), `project.production_branch` (= `main` or `master`).
- `SOLVER_GITHUB_TOKEN`.

**Steps:**
1. Read repo + both branches from `/tmp/issue.json`.
2. `git clone --depth 50 --no-single-branch --branch <prod_branch> <auth-url> ./client-repo`.
3. Configure git user as `Solver Agent <solver@roman-technologies.dev>`.
4. `git fetch --depth 50 origin <dev_branch>` (best-effort; OK if branch missing).
5. If fetch succeeded: write `git rev-parse origin/<dev_branch>` to `/tmp/prev-solver-sha`. Otherwise write empty string.
6. `git checkout -B <dev_branch> origin/<prod_branch>` — working tree now matches production HEAD, on a local branch named `cms-preview`.

**Why reset?** Production may have moved forward of `cms-preview` (Stefan committed directly to `main`/`master`). Resetting guarantees the S1.5 listener can fast-forward production to `cms-preview` after the agent commits, regardless of any drift.

**Outputs:**
- `./client-repo/` at `origin/<prod_branch>` HEAD, branch `cms-preview` checked out.
- `/tmp/prev-solver-sha` — previous `cms-preview` SHA (empty on first run).

**Failure messages:**
- 401/403 on clone → PAT scope drift; surface "git clone failed: <code>".
- 404 on clone → repo missing; surface "Repo not found".
- Fetch of `<dev_branch>` failing is non-fatal (first-run); prev-sha just stays empty.
